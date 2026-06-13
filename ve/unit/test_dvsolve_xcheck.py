"""Phase E / E1 — XCHECK differential cross-check (dv-solve vs Boolector).

XCHECK (``VSC_DVSOLVE_XCHECK=1``) re-checks every model dv-solve produces against
Boolector: the bare problem's SAT/UNSAT verdict must agree, and the dv-solve
model must be a *valid* model (membership). Value streams legitimately differ
between engines, so XCHECK compares semantic agreement, never exact values.

Coverage:
  * T-E1a verdict + membership agreement on a clean corpus; the mode can FAIL
    (a deliberately corrupted model is caught).
  * T-E1b membership over N draws on the historically-buggy shapes (``~`` bitwise
    invert, signed/unsigned compares, dist, randsz, wide >64-bit).
  * T-E1c strided sampling is deterministic / reproducible.
  * T-E1d warn-mode tallies instead of raising.

See doc/notes/dv_solve_phaseE_selfsufficiency_plan.md (E1). Skipped when the
dv-solve native library is unavailable.
"""
import random
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solver import xcheck
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


def _boolector_available():
    try:
        return select_backend("boolector").available()
    except Exception:
        return False


@contextmanager
def _xcheck(warn=False, rate=None):
    """Enable XCHECK for the block and yield the live tally getter."""
    prev = xcheck.set_xcheck(True, warn=warn, rate=rate)
    xcheck.reset_tally()
    try:
        yield xcheck.get_tally
    finally:
        xcheck.restore_xcheck(prev)


@contextmanager
def _corrupt_first_field(transform):
    """Monkeypatch the dv-solve back-end to corrupt the first rand field's value
    after a real solve, so XCHECK has a genuine mismatch to catch. ``transform``
    maps (val, other_vals) -> new bad val."""
    orig = dvb.DvSolveBackend.solve_randset

    def _bad(self, rs, *a, **k):
        orig(self, rs, *a, **k)
        fields = [f for f in rs.all_fields() if getattr(f, "is_used_rand", False)]
        if fields:
            others = [int(f.get_val()) for f in fields[1:]]
            fields[0].set_val(transform(int(fields[0].get_val()), others))

    dvb.DvSolveBackend.solve_randset = _bad
    try:
        yield
    finally:
        dvb.DvSolveBackend.solve_randset = orig


@unittest.skipUnless(_dvsolve_available() and _boolector_available(),
                     "dv-solve and Boolector both required for XCHECK")
class TestDvSolveXCheck(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _run(self, factory, n=30, seed=0):
        random.seed(seed)
        obj = factory()
        for _ in range(n):
            obj.randomize()
        return obj

    # ------------------------------------------------------------------ #
    # T-E1a — clean agreement, and the mode can actually FAIL              #
    # ------------------------------------------------------------------ #
    def test_te1a_clean_agreement(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a < s.b
                s.b < 200

        with _xcheck() as tally:
            self._run(C, n=50)
            t = tally()
        self.assertEqual(t["mismatch"], 0, "unexpected XCHECK mismatch: %s" % t)
        self.assertEqual(t["checked"], 50, t)
        self.assertEqual(t["error"], 0, t)

    def test_te1a_catches_bad_model(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a < s.b
                s.b < 200

        # Force a := b (violates the strict a < b) after a real solve.
        with _corrupt_first_field(lambda a, others: others[0] if others else a):
            with _xcheck():
                with self.assertRaises(xcheck.XCheckMismatch):
                    self._run(C, n=10)

    # ------------------------------------------------------------------ #
    # T-E1b — membership on the historically-buggy shapes                  #
    # ------------------------------------------------------------------ #
    def test_te1b_bitwise_invert(self):
        # `~` must be a *bitwise* invert (the soundness bug fixed in the sampler
        # plan §2.10); XCHECK membership would catch a regression to logical not.
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a == ~s.b

        with _xcheck() as tally:
            self._run(C, n=40)
            t = tally()
        self.assertEqual(t["mismatch"], 0, t)

    def test_te1b_signed_compare(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_int8_t()
                s.b = vsc.rand_int8_t()
            @vsc.constraint
            def c(s):
                s.a < 0
                s.b > 0
                s.a < s.b

        with _xcheck() as tally:
            self._run(C, n=40)
            t = tally()
        self.assertEqual(t["mismatch"], 0, t)

    def test_te1b_dist(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((1, 3), 1), vsc.weight((200, 255), 2)])

        with _xcheck() as tally:
            self._run(C, n=60)
            t = tally()
        self.assertEqual(t["mismatch"], 0, t)

    def test_te1b_randsz(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.uint16_t())
            @vsc.constraint
            def sc(s):
                s.l.size.inside(vsc.rangelist(0, 1, 2, 4, 8))
            @vsc.constraint
            def vc(s):
                with vsc.foreach(s.l, idx=True) as idx:
                    s.l[idx] == idx

        with _xcheck() as tally:
            self._run(C, n=40)
            t = tally()
        self.assertEqual(t["mismatch"], 0, t)

    def test_te1b_wide(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(96)
            @vsc.constraint
            def c(s):
                s.a < 1000000

        with _xcheck() as tally:
            self._run(C, n=40)
            t = tally()
        self.assertEqual(t["mismatch"], 0, t)

    def test_te1b_clog2_implies_arith(self):
        # F-E3 regression: an implication whose guard is a logical AND of
        # comparisons over lifted arithmetic (clog2) must produce CORRECT values
        # — historically dv-solve left the consequent unconstrained (a = garbage)
        # because the *primary* bounds engine's disjunction propagation is
        # unsound, which XCHECK caught. F-E3 deferred the shape; Phase F / F-2 now
        # serves it natively by routing such RandSets to the complete BV-SAT
        # engine (force-serve) instead of the fallback. This locks the *values*
        # (catches a future regression to a native-but-wrong encoding) AND
        # confirms it is now served natively (no `implies-aux` fallback).
        import math
        import vsc.model.randomizer as rndmod

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(8)
                s.b = vsc.rand_bit_t(8)
            @vsc.constraint
            def clog2_c(s):
                with vsc.implies((s.b >= 0) & (s.b < 2)):
                    s.a == 0
                for i in range(1, 8):
                    with vsc.implies(((s.b - 1) >= (2 ** (i - 1)))
                                     & ((s.b - 1) < (2 ** i))):
                        s.a == i

        c = C()
        with _xcheck() as tally:
            for i in range(1, 64):
                with c.randomize_with():
                    c.b == i
                expect = 0 if i < 2 else math.ceil(math.log2(i))
                self.assertEqual(int(c.a), expect,
                                 "clog2(%d): a=%d, expected %d" % (i, int(c.a),
                                                                   expect))
            self.assertEqual(tally()["mismatch"], 0)

        # Confirm it is now SERVED NATIVELY (force-served via BV-SAT), not
        # deferred — no `implies-aux` fallback — while still correct (a==clog2).
        snap = rndmod.snapshot_fallback_tally()
        rndmod.set_fallback_tally(True)
        rndmod.reset_fallback_tally()
        try:
            c2 = C()
            with c2.randomize_with():
                c2.b == 5
            self.assertEqual(int(c2.a), 3, "clog2(5) should be 3")
            self.assertNotIn(
                "implies-aux", rndmod.get_fallback_tally(),
                "clog2 guard should be served natively (BV-SAT), not deferred")
        finally:
            rndmod.restore_fallback_tally(snap)

    # ------------------------------------------------------------------ #
    # T-E1c — strided sampling is deterministic                            #
    # ------------------------------------------------------------------ #
    def test_te1c_sampling_deterministic(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a < 100

        def run_rate(rate):
            with _xcheck(rate=rate) as tally:
                self._run(C, n=20)
                return tally()

        full = run_rate(1.0)
        half = run_rate(0.5)
        quarter = run_rate(0.25)
        self.assertEqual(full["checked"], 20)
        self.assertEqual(half["checked"], 10)
        self.assertEqual(half["skipped"], 10)
        self.assertEqual(quarter["checked"], 5)
        # Reproducible run-to-run.
        self.assertEqual(run_rate(0.5)["checked"], 10)

    # ------------------------------------------------------------------ #
    # T-E1d — warn mode tallies instead of raising                        #
    # ------------------------------------------------------------------ #
    def test_te1d_warn_mode(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a < s.b
                s.b < 200

        with _corrupt_first_field(lambda a, others: others[0] if others else a):
            with _xcheck(warn=True) as tally:
                # Must NOT raise in warn mode.
                self._run(C, n=5)
                t = tally()
        self.assertGreater(t["mismatch"], 0, "warn mode should tally mismatches")


if __name__ == "__main__":
    unittest.main()
