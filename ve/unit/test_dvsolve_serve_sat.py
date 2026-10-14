"""Phase F / F-3a: dv-solve serves the problems it proves SAT.

A RandSet the primary search cannot decide, but BV-SAT proves SAT, is served
by dv-solve (uniform sampler), with or without Boolector installed. The
`VSC_DVSOLVE_BVSAT_SERVE_SAT=0` opt-out, which deferred it to Boolector, is
gone (v2 plan V24). Boolector runs only where dv-solve has a gap (a reason
code such as ``width``) and the fallback is enabled
(``VSC_DVSOLVE_FALLBACK=boolector``), and the Randomizer builds it only on the
first such defer, so a randomize dv-solve serves never imports pyboolector.

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
class _SatDeferShape(object):
    # A shape the CDCL compile leaves out, so BV-SAT *proves it SAT* and
    # serves it, deterministically. A uint32 compared with non-rand uint8 fields elaborates
    # to `t != <SV cast>`, which the CDCL engine does not compile (today; when
    # it does, pick another uncompiled shape: run with DV_LOG=<file> and look
    # for `cdcl-uncompiled`). It was `x > 2**63` on a u64 until v2 plan V17
    # made that native.
    def __init__(s):
        s.t = vsc.rand_uint32_t()
        s.a = vsc.uint8_t(3)
        s.b = vsc.uint8_t(9)

    @vsc.constraint
    def sc(s):
        s.t != s.a
        s.t != s.b
        s.t < 20


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveServeSatAuto(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()   # these tests observe back-end dispatch
        self._saved = (rnd._FALLBACK, rnd._NO_FALLBACK, dvb._BVSAT_SAMPLER)

    def tearDown(self):
        rnd._FALLBACK, rnd._NO_FALLBACK, dvb._BVSAT_SAMPLER = self._saved
        ctor.set_solver_backend(None)
        super().tearDown()

    # ------------------------------------------------------------------ #
    # End-to-end                                                           #
    # ------------------------------------------------------------------ #
    def _deferred_codes(self, n=8):
        """Run the BV-SAT shape `n` times and return the reason codes of any
        defers it produced."""
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            obj = _SatDeferShape()
            for _ in range(n):
                obj.randomize()
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        return {k.split(":")[0] for k in hist}

    def test_serves_natively(self):
        # With Boolector installed or not, the SAT shape is served in dv-solve:
        # nothing is deferred.
        self.assertEqual(self._deferred_codes(), set())

    def test_ordered_without_sampler_still_served(self):
        # An ordered RandSet the staged sampler does not take (here: sampler
        # off) is served without the ordering, which shapes the distribution
        # only. It deferred (`bvsat-sat-deferred`) before V24.
        rnd._NO_FALLBACK = True
        dvb._BVSAT_SAMPLER = False

        @vsc.randobj
        class Ordered(_SatDeferShape):
            def __init__(s):
                super().__init__()
                s.u = vsc.rand_uint8_t()

            @vsc.constraint
            def oc(s):
                vsc.solve_order(s.t, s.u)
                s.u < s.t

        obj = Ordered()
        for _ in range(8):
            obj.randomize()
            self.assertTrue(obj.t < 20 and obj.t not in (3, 9)
                            and obj.u < obj.t, (obj.t, obj.u))

    def test_served_randomize_builds_no_fallback(self):
        # F-3c: a randomize dv-solve serves never resolves the Boolector
        # back-end, so pyboolector is not imported for it.
        calls = []
        orig = rnd.select_backend

        def spy(name):
            calls.append(name)
            return orig(name)
        rnd.select_backend = spy
        try:
            obj = _SatDeferShape()
            for _ in range(4):
                obj.randomize()
        finally:
            rnd.select_backend = orig
        self.assertNotIn("boolector", calls)

    @requires_boolector
    def test_gap_still_falls_back(self):
        # With the fallback enabled, a real gap (a field wider than dv-solve
        # can encode) is served by Boolector, built on the first defer. The
        # cap is lowered so Boolector's solve stays small.
        rnd._FALLBACK = True
        saved_cap, dvb._MAX_FIELD_WIDTH = dvb._MAX_FIELD_WIDTH, 300
        self.addCleanup(setattr, dvb, "_MAX_FIELD_WIDTH", saved_cap)

        @vsc.randobj
        class Wide(object):
            def __init__(self):
                self.w = vsc.rand_bit_t(dvb._MAX_FIELD_WIDTH + 1)

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
