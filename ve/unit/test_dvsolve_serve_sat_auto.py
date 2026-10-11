"""Phase F / T-F1a — serve-SAT default is `auto`, decoupled from the fallback.

F-1a makes `VSC_DVSOLVE_BVSAT_SERVE_SAT` a tri-state with `auto` as the default:

  * ``"1"``    — always serve satisfiable problems from BV-SAT (uniform sampler);
  * ``"0"``    — never; defer SAT to the external fallback (the Phase-A posture);
  * ``"auto"`` — serve SAT from BV-SAT *only when no external fallback is
                 available* to serve it. The Randomizer sets the per-instance
                 ``_external_fallback_available`` from its fallback chain.

The point of `auto` is to decouple the serve-SAT *cost* from the *default*: while
Boolector is still the default fallback, `auto` behaves exactly like `"0"` (defer
cheaply); once the fallback is dropped (F-3) dv-solve serves SAT itself with no
second flip. These tests lock both the decision logic and the end-to-end posture.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.rand_state import RandState
from vsc.model.solver.backend import select_backend
from vsc.model.solver.dvsolve_backend import DvSolveBackend
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase, requires_boolector


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@vsc.randobj
class _UpperHalfConstBound(object):
    # `x > 2**63` on an unsigned u64: a constant bound in the unsigned upper half.
    # The literal is inferred signed (width 65) and lowered to a concat wide-const
    # the comparison compiler can't fold, so the constraint is left uncompiled and
    # BV-SAT *proves it SAT* — exactly the `bvsat-sat-deferred` (serve / defer)
    # decision point, and deterministic. (A gapped value-set / multi-range
    # membership is no longer a valid example — Phase G's native EXPR_IN_RANGES
    # membership solves those directly.)
    def __init__(s):
        s.x = vsc.rand_bit_t(64)

    @vsc.constraint
    def sc(s):
        s.x > (1 << 63)


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveServeSatAuto(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()   # these tests observe back-end dispatch
        self._saved_mode = dvb._BVSAT_SERVE_SAT_MODE

    def tearDown(self):
        dvb._BVSAT_SERVE_SAT_MODE = self._saved_mode
        ctor.set_solver_backend(None)
        super().tearDown()

    # ------------------------------------------------------------------ #
    # The decision function, exhaustively                                  #
    # ------------------------------------------------------------------ #
    def test_serve_sat_enabled_matrix(self):
        be = DvSolveBackend()
        cases = {
            # (mode, external_fallback_available) -> expected serve-SAT
            ("on", True): True,
            ("on", False): True,
            ("off", True): False,
            ("off", False): False,
            ("auto", True): False,   # fallback present → defer (== "0" today)
            ("auto", False): True,   # nothing else will serve → serve (post F-3)
        }
        for (mode, has_fb), expected in cases.items():
            dvb._BVSAT_SERVE_SAT_MODE = mode
            be._external_fallback_available = has_fb
            self.assertEqual(
                be._serve_sat_enabled(), expected,
                "mode=%r external_fallback_available=%r" % (mode, has_fb))

    def test_default_mode_is_auto(self):
        # With no env override the mode resolves to `auto` (F-1a default).
        import os
        saved = os.environ.pop("VSC_DVSOLVE_BVSAT_SERVE_SAT", None)
        try:
            self.assertEqual(dvb._serve_sat_mode(), "auto")
        finally:
            if saved is not None:
                os.environ["VSC_DVSOLVE_BVSAT_SERVE_SAT"] = saved

    # ------------------------------------------------------------------ #
    # The Randomizer wires the per-instance fallback availability          #
    # ------------------------------------------------------------------ #
    def test_randomizer_sets_fallback_availability(self):
        be = DvSolveBackend()
        r = rnd.Randomizer(RandState(0), backend=be)
        self.assertEqual(
            be._external_fallback_available, bool(r.fallback_backends),
            "Randomizer must set _external_fallback_available from its chain")

    # ------------------------------------------------------------------ #
    # End-to-end: the SAT-deferring shape, per mode                        #
    # ------------------------------------------------------------------ #
    def _deferred_codes(self, n=8):
        """Run the upper-half const-bound SAT shape `n` times and return the set
        of `bvsat-sat-deferred` tally keys it produced."""
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            obj = _UpperHalfConstBound()
            for _ in range(n):
                obj.randomize()
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        return {k for k in hist if k.split(":")[0] == "bvsat-sat-deferred"}

    @requires_boolector
    def test_auto_defers_while_fallback_present(self):
        # Normal config: Boolector is the fallback, so `auto` == `"0"` — the SAT
        # shape defers (served by the net), behavior unchanged from pre-F-1.
        dvb._BVSAT_SERVE_SAT_MODE = "auto"
        self.assertNotEqual(self._deferred_codes(), set(),
                            "auto with a fallback present should defer SAT")

    @requires_boolector
    def test_explicit_off_defers(self):
        dvb._BVSAT_SERVE_SAT_MODE = "off"
        self.assertNotEqual(self._deferred_codes(), set(),
                            "off should always defer SAT to the fallback")

    def test_explicit_on_serves_natively(self):
        # Opt-in serve: dv-solve serves the SAT shape itself, deferring nothing.
        dvb._BVSAT_SERVE_SAT_MODE = "on"
        self.assertEqual(self._deferred_codes(), set(),
                         "on should serve SAT natively (no bvsat-sat-deferred)")

    def test_served_sum_keeps_carry_into_wider_lhs(self):
        # `c32 == a16 + b16` must hold at 32 bits. The translator materialized
        # the sum into a 32-bit aux and then zero-extended it "from 16 bits",
        # dropping the carry, so ~half of the served solutions had
        # c == (a + b) mod 2**16. Only the self-served path (no Boolector, or
        # mode "on") saw it -- `auto` defers this shape to Boolector -- and
        # VSC_DVSOLVE_VALIDATE could not, since it checks the model against the
        # same mistranslated formula.
        dvb._BVSAT_SERVE_SAT_MODE = "on"

        @vsc.randobj
        class Sum(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(16)
                self.c = vsc.rand_bit_t(32)

            @vsc.constraint
            def cc(self):
                self.c == self.a + self.b
                self.a > 0
                self.b > 0

        obj = Sum()
        for _ in range(100):
            obj.randomize()
            self.assertEqual(int(obj.c), int(obj.a) + int(obj.b))


if __name__ == "__main__":
    unittest.main()
