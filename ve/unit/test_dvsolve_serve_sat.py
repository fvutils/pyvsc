"""Phase F / F-3a — dv-solve serves the problems it proves SAT.

`VSC_DVSOLVE_BVSAT_SERVE_SAT` defaults to ``"1"``: a RandSet the primary search
cannot decide, but BV-SAT proves SAT, is served by dv-solve (uniform sampler)
even when Boolector is installed. Boolector runs only where dv-solve has a gap
(a reason code such as ``width``), and the Randomizer builds it only on the
first such defer, so a randomize dv-solve serves never imports pyboolector.

  * ``"1"``    — (default) serve SAT from BV-SAT;
  * ``"0"``    — never; defer SAT to the external fallback (the A/B opt-out);
  * ``"auto"`` — the F-1a default, which deferred whenever Boolector was
                 installed; now the same as ``"1"``.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
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
    # The mode                                                             #
    # ------------------------------------------------------------------ #
    def test_mode_parsing(self):
        import os
        saved = os.environ.pop("VSC_DVSOLVE_BVSAT_SERVE_SAT", None)
        try:
            self.assertEqual(dvb._serve_sat_mode(), "on", "default")
            for raw, expected in (("1", "on"), ("0", "off"), ("auto", "on"),
                                  ("AUTO", "on")):
                os.environ["VSC_DVSOLVE_BVSAT_SERVE_SAT"] = raw
                self.assertEqual(dvb._serve_sat_mode(), expected, raw)
        finally:
            os.environ.pop("VSC_DVSOLVE_BVSAT_SERVE_SAT", None)
            if saved is not None:
                os.environ["VSC_DVSOLVE_BVSAT_SERVE_SAT"] = saved

    def test_serve_sat_enabled(self):
        be = DvSolveBackend()
        for mode, expected in (("on", True), ("off", False)):
            dvb._BVSAT_SERVE_SAT_MODE = mode
            self.assertEqual(be._serve_sat_enabled(), expected, mode)

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

    def test_default_serves_natively(self):
        # With Boolector installed or not, the default serves the SAT shape in
        # dv-solve: nothing is deferred.
        import os
        saved = os.environ.pop("VSC_DVSOLVE_BVSAT_SERVE_SAT", None)
        try:
            dvb._BVSAT_SERVE_SAT_MODE = dvb._serve_sat_mode()
        finally:
            if saved is not None:
                os.environ["VSC_DVSOLVE_BVSAT_SERVE_SAT"] = saved
        self.assertEqual(self._deferred_codes(), set(),
                         "the default should serve SAT natively")

    @requires_boolector
    def test_explicit_off_defers(self):
        dvb._BVSAT_SERVE_SAT_MODE = "off"
        self.assertNotEqual(self._deferred_codes(), set(),
                            "off should always defer SAT to the fallback")

    def test_served_randomize_builds_no_fallback(self):
        # F-3c: a randomize dv-solve serves never resolves the Boolector
        # back-end, so pyboolector is not imported for it.
        dvb._BVSAT_SERVE_SAT_MODE = "on"
        calls = []
        orig = rnd.select_backend

        def spy(name):
            calls.append(name)
            return orig(name)
        rnd.select_backend = spy
        try:
            obj = _UpperHalfConstBound()
            for _ in range(4):
                obj.randomize()
        finally:
            rnd.select_backend = orig
        self.assertNotIn("boolector", calls)

    @requires_boolector
    def test_gap_still_falls_back(self):
        # A real gap (a field wider than 255 bits) is still served by
        # Boolector, built on the first defer.
        @vsc.randobj
        class Wide(object):
            def __init__(self):
                self.w = vsc.rand_bit_t(300)

            @vsc.constraint
            def wc(self):
                self.w > 5

        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            obj = Wide()
            for _ in range(4):
                obj.randomize()
                self.assertGreater(int(obj.w), 5)
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        self.assertEqual(hist.get("width"), 4, hist)

    def test_served_sum_keeps_carry_into_wider_lhs(self):
        # `c32 == a16 + b16` must hold at 32 bits. The translator materialized
        # the sum into a 32-bit aux and then zero-extended it "from 16 bits",
        # dropping the carry, so ~half of the served solutions had
        # c == (a + b) mod 2**16. Only the self-served path saw it (before
        # F-3a, the default deferred this shape to Boolector) -- and
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
