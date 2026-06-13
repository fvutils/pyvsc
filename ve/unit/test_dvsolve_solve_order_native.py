"""Phase F / T-F2a — dv-solve serves `solve_order` RandSets natively.

Before F-2a, an order-bearing RandSet (`rs.rand_order_l` set) that the primary
bounds engine couldn't decide was proved SAT by BV-SAT and then *deferred for
serving* to Boolector (`reason_code="bvsat-sat-deferred"`) — the uniform sampler
has no notion of solve order. F-2a added **staged sampling** (`bvsat_sampler.
sample_ordered`): per order stage, pin a random domain value and assert it (the
Boolector swizzler's assume→assert), so dv-solve serves the values itself and
honors the ordering's distribution.

These tests lock both halves with serve-SAT forced on in-process:
  * **native serve** — the order-bearing RandSet defers *nothing*
    (no `bvsat-sat-deferred` in the tally);
  * **order semantics** — the canonical `c==0 -> a==0` shape with `a` solved
    first yields `a > 0` on *every* draw (the `test_before_and_after_lists`
    property), which a joint-uniform sample would violate ~50% of the time.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveSolveOrderNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        # Force serve-SAT on (default is off): the path under test only serves
        # SAT models when serve-SAT is enabled.
        self._saved_serve = dvb._BVSAT_SERVE_SAT
        dvb._BVSAT_SERVE_SAT = True

    def tearDown(self):
        dvb._BVSAT_SERVE_SAT = self._saved_serve
        ctor.set_solver_backend(None)
        super().tearDown()

    @staticmethod
    def _ordered_obj():
        @vsc.randobj
        class my_c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(64)
                s.b = vsc.rand_bit_t(64)
                s.c = vsc.rand_bit_t(1)

            @vsc.constraint
            def abc_c(s):
                # Solving a (or b) first makes a==0 essentially impossible:
                # a is pinned to a random 64-bit value, forcing c != 0.
                with vsc.implies(s.c == 0):
                    s.a == 0
                    s.b == 0
        return my_c()

    def test_solve_order_served_natively(self):
        """The order-bearing RandSet must defer nothing — dv-solve serves it."""
        obj = self._ordered_obj()
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            for _ in range(40):
                with obj.randomize_with():
                    vsc.solve_order(obj.a, obj.c)
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        deferred = {k: v for k, v in hist.items()
                    if k.split(":")[0] == "bvsat-sat-deferred"}
        self.assertEqual(
            deferred, {},
            "order-bearing RandSet deferred for serving instead of being served "
            "natively by staged sampling: %s" % hist)

    def test_solve_order_distribution(self):
        """Solving `a` before `c` must force `a > 0` on every draw (the order
        semantic; a joint-uniform sample would give a==0 ~half the time)."""
        obj = self._ordered_obj()
        samples = 80
        a_pos = 0
        for _ in range(samples):
            with obj.randomize_with():
                vsc.solve_order(obj.a, obj.c)
            if int(obj.a) > 0:
                a_pos += 1
        self.assertEqual(
            a_pos, samples,
            "solve_order(a, c) did not honor ordering: a>0 on %d/%d draws "
            "(expected all)" % (a_pos, samples))


if __name__ == "__main__":
    unittest.main()
