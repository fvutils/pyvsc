"""V1 (fallback_elimination_v2_plan.md, bug B1) — the BV-SAT samplers pin
negative values of signed fields correctly.

``sample_ordered``, ``sample_dist`` and ``sample_dist_conditional`` freeze a
chosen value as ``var == expr_const(v)``. ``expr_const`` is unsized, so the
carrier must hold the field's *value*. ``_pack_const64`` used to mask every
value to the field width, turning -7 on an int32 into ``2^32-7``; the pin was
then unsatisfiable. Effects, each locked by a test below:
  * ordered draws never pinned a negative target, skewing them non-negative;
  * a stage that fell back to sampling and drew a negative value pinned it
    wrongly, so the next stage was UNSAT and the RandSet deferred to Boolector
    (riscv-dv ``riscv_loop_test``);
  * negative ``dist`` targets on a signed field lost their weighting.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc.model.solver.bvsat_sampler import _pack_const64
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _strict_no_fallback():
    """VSC_DVSOLVE_NO_FALLBACK strict mode: a deferral raises instead of
    falling back to Boolector."""
    saved = rnd._NO_FALLBACK
    rnd._NO_FALLBACK = True
    try:
        yield
    finally:
        rnd._NO_FALLBACK = saved


class TestPackConst64(unittest.TestCase):

    def test_signed_negative_keeps_value(self):
        self.assertEqual(_pack_const64(-7, 32, True), -7)
        self.assertEqual(_pack_const64(-128, 8, True), -128)
        self.assertEqual(_pack_const64(-1, 64, True), -1)

    def test_signed_positive_unchanged(self):
        self.assertEqual(_pack_const64(127, 8, True), 127)
        self.assertEqual(_pack_const64((1 << 63) - 1, 64, True), (1 << 63) - 1)

    def test_unsigned_masked(self):
        self.assertEqual(_pack_const64(255, 8, False), 255)
        self.assertEqual(_pack_const64(0xFFFFFFFF, 32, False), 0xFFFFFFFF)

    def test_uint64_upper_half_two_complement(self):
        self.assertEqual(_pack_const64((1 << 64) - 1, 64, False), -1)
        self.assertEqual(_pack_const64(1 << 63, 64, False), -(1 << 63))


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveSignedPin(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        # The ordered sampler only serves SAT models with serve-SAT on.
        self._saved_serve = dvb._BVSAT_SERVE_SAT_MODE
        dvb._BVSAT_SERVE_SAT_MODE = "on"

    def tearDown(self):
        dvb._BVSAT_SERVE_SAT_MODE = self._saved_serve
        ctor.set_solver_backend(None)
        super().tearDown()

    def _ordered_signed_chi2(self, width):
        """Solving signed ``a`` first gives ``a`` uniform over its domain: chi^2
        over four equal quarters of the range."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_int_t(width)
                s.b = vsc.rand_int_t(width)
                s.c = vsc.rand_bit_t(1)

            @vsc.constraint
            def cc(s):
                with vsc.implies(s.c == 0):    # conjunctive body -> BV-SAT
                    s.a == 0
                    s.b == 0

        obj = C()
        n = 400
        q = 1 << (width - 2)
        lo = -(1 << (width - 1))
        counts = [0] * 4
        with _strict_no_fallback():
            for _ in range(n):
                with obj.randomize_with():
                    vsc.solve_order(obj.a, obj.c)
                counts[(int(obj.a) - lo) // q] += 1
        exp = n / 4.0
        chi2 = sum((k - exp) ** 2 / exp for k in counts)
        # 3 dof, p = 0.001 -> 16.27. Before the fix both negative quarters
        # were empty (chi^2 ~ 400).
        self.assertLess(chi2, 16.27,
                        "int%d ordered draw not uniform over sign: quarters=%s "
                        "chi2=%.1f" % (width, counts, chi2))

    def test_ordered_signed_int8_uniform(self):
        self._ordered_signed_chi2(8)

    def test_ordered_signed_int32_uniform(self):
        self._ordered_signed_chi2(32)

    def test_ordered_stage_sampled_negative_no_defer(self):
        """riscv_loop_test shape: an early stage whose random domain targets
        almost never land (``init`` in [-10, -1] out of an int32 domain) is
        served by a constrained sample, which draws a negative value. That value
        is then pinned for the later stages; a wrong pin made the next stage
        UNSAT and deferred the RandSet."""
        @vsc.randobj
        class Loop(object):
            def __init__(s):
                s.init = vsc.rand_int32_t()
                s.limit = vsc.rand_int32_t()
                s.step = vsc.rand_int32_t()
                s.en = vsc.rand_bit_t(1)

            @vsc.constraint
            def cc(s):
                s.init >= -10
                s.init <= -1
                s.limit >= -10
                s.limit <= 10
                s.step >= 1
                s.step <= 4
                s.limit > s.init
                with vsc.implies(s.en == 0):   # conjunctive body -> BV-SAT
                    s.limit == 0
                    s.step == 1

        obj = Loop()
        rnd.set_fallback_tally(True)
        snap = rnd.snapshot_fallback_tally()
        rnd.reset_fallback_tally()
        try:
            with _strict_no_fallback():
                for _ in range(40):
                    with obj.randomize_with():
                        vsc.solve_order(obj.init, obj.limit)
                        vsc.solve_order(obj.limit, obj.step)
                    init, limit, step = (int(obj.init), int(obj.limit),
                                         int(obj.step))
                    self.assertTrue(-10 <= init <= -1, init)
                    self.assertTrue(init < limit <= 10, (init, limit))
                    self.assertTrue(1 <= step <= 4, step)
                    if int(obj.en) == 0:
                        self.assertEqual((limit, step), (0, 1))
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        self.assertEqual(hist, {})

    def test_dist_negative_targets_on_signed_field(self):
        """A dist with negative targets on a signed field, force-served via
        BV-SAT (``sample_dist``), keeps its weighting."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_int16_t()
                s.b = vsc.rand_int16_t()
                s.en = vsc.rand_bit_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(-300, 99999), vsc.weight(300, 1)])
                with vsc.implies(s.en == 0):   # conjunctive body -> BV-SAT
                    s.a == 300
                    s.b == 0

        obj = C()
        n = 200
        neg = 0
        with _strict_no_fallback():
            for _ in range(n):
                with obj.randomize_with() as it:
                    it.en == 1                 # guard false -> a weighted
                a = int(obj.a)
                self.assertIn(a, (-300, 300))
                neg += (a == -300)
        # ~99.999% expected; the bug lost the weighting (~50%).
        self.assertGreater(neg, int(0.85 * n),
                           "negative dist target lost its weighting: %d/%d"
                           % (neg, n))


if __name__ == "__main__":
    unittest.main()
