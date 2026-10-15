"""BV-SAT serving through the engine's sampler (v2 plan V19).

A RandSet served by BV-SAT (a field over 64 bits, or one the primary engine
cannot compile soundly) is drawn by ``dvs_bbsolver_sample``: bit-blasted once,
with the XOR planes as assumptions, instead of re-blasted at every plane level.
The sampler also gives the SAT/UNSAT verdict, so there is no separate check,
and a repeated ``randomize()`` keeps the encoded instance in the plan cache and
only solves again.

Skipped when the dv-solve native library, or its CaDiCaL backend, is
unavailable.
"""
import collections
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solve_failure import SolveFailure
import vsc.model.solver.bvsat_sampler as bs
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _native_available():
    try:
        if not select_backend("dv-solve").available():
            return False
        from dv_solve.builder import SolveProblemBuilder
        b = SolveProblemBuilder()
        b.add_var(0, 8, False, 0, 255)
        buf, _ = b.finalize()
        b.destroy()
        bb = bs.open_native(buf)
        if bb is None:
            return False
        bb.destroy()
        return True
    except Exception:
        return False


def _wide(W=200, bound=None):
    @vsc.randobj
    class C(object):
        def __init__(s):
            s.a = vsc.rand_bit_t(W)
            s.b = vsc.rand_bit_t(W)
            s.k = vsc.bit_t(8)

        @vsc.constraint
        def cc(s):
            s.a < s.b
            if bound is not None:
                s.b < bound
            s.a[7:0] != s.k
    return C()


@unittest.skipUnless(_native_available(), "dv-solve native sampler not available")
class TestDvSolveNativeSampler(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()
        self._saved = bs._NATIVE

    def tearDown(self):
        bs._NATIVE = self._saved
        ctor.set_solver_backend(None)
        super().tearDown()

    def _count_contexts(self):
        """Count BVSatCtx constructions (any kind) from here on."""
        from dv_solve import bvsat
        made = []
        orig = bvsat.BVSatCtx.__init__

        def init(this, *a, **kw):
            made.append(kw.get("incremental", False))
            orig(this, *a, **kw)
        bvsat.BVSatCtx.__init__ = init
        self.addCleanup(setattr, bvsat.BVSatCtx, "__init__", orig)
        return made

    def test_small_problem_gets_a_fresh_context(self):
        """Below _BVSAT_KEEP_MIN_ANDS a reused instance costs more than a new
        encode: one incremental context per randomize(), and no separate
        check context."""
        obj = _wide()
        made = self._count_contexts()
        for _ in range(4):
            obj.randomize()
            self.assertLess(int(obj.a), int(obj.b))
        self.assertEqual(made, [True] * 4)

    def test_kept_plan_only_draws(self):
        """A kept instance serves later randomize() calls without building
        anything; a changed constant rebuilds it."""
        saved = dvb._BVSAT_KEEP_MIN_ANDS
        dvb._BVSAT_KEEP_MIN_ANDS = 0
        self.addCleanup(setattr, dvb, "_BVSAT_KEEP_MIN_ANDS", saved)
        obj = _wide()
        made = self._count_contexts()
        for i in range(5):
            obj.k = i
            obj.randomize()
            a, b = int(obj.a), int(obj.b)
            self.assertLess(a, b)
            self.assertNotEqual(a & 0xFF, i)
        # `k` changed every call, so every call rebuilt: one context each.
        self.assertEqual(made, [True] * 5)

        made.clear()
        for _ in range(5):
            obj.randomize()
            self.assertLess(int(obj.a), int(obj.b))
        # Same structure since call 1 (admitted from call 2) and now the same
        # `k`: the plan kept by the last build is drawn from, nothing built.
        self.assertEqual(made, [])
        plans = [getattr(f, dvb._PLAN_ATTR, None) for f in obj.get_model().field_l]
        self.assertTrue(any(p is not None and p.sample_vars is not None
                            for p in plans))

    def test_constant_change_after_reuse(self):
        """A plan drawn from again still follows a changed constant."""
        saved = dvb._BVSAT_KEEP_MIN_ANDS
        dvb._BVSAT_KEEP_MIN_ANDS = 0
        self.addCleanup(setattr, dvb, "_BVSAT_KEEP_MIN_ANDS", saved)
        obj = _wide()
        obj.k = 7
        for _ in range(4):
            obj.randomize()
        for k in (3, 9, 200):
            obj.k = k
            for _ in range(5):
                obj.randomize()
                self.assertNotEqual(int(obj.a) & 0xFF, k)

    def test_small_range_on_a_wide_field_is_covered(self):
        """`a < b < 21` on 200-bit fields: every value of `a` (0..19) is
        drawn, roughly evenly."""
        obj = _wide(bound=21)
        obj.k = 255               # no a in 0..19 has low byte 255
        hist = collections.Counter()
        n = 400
        for _ in range(n):
            obj.randomize()
            hist[int(obj.a)] += 1
        self.assertEqual(set(hist), set(range(20)))
        # (a, b) pairs: a is weighted toward small values (20 - a choices of
        # b), so check against that, not flat: chi-square, 19 dof, p = 0.001.
        total = sum(20 - a for a in range(20))
        chi2 = sum((hist[a] - n * (20 - a) / total) ** 2 / (n * (20 - a) / total)
                   for a in range(20))
        self.assertLess(chi2, 43.8, sorted(hist.items()))

    def test_unsat_is_reported(self):
        obj = _wide(bound=1)      # a < b < 1 has no solution
        with self.assertRaises(SolveFailure):
            obj.randomize()

    def test_python_loop_still_serves(self):
        """With the native sampler off, the Python level loop serves."""
        bs._NATIVE = False
        obj = _wide(bound=21)
        seen = set()
        for _ in range(20):
            obj.randomize()
            self.assertLess(int(obj.a), int(obj.b))
            self.assertLess(int(obj.b), 21)
            seen.add(int(obj.a))
        self.assertGreater(len(seen), 5)


if __name__ == "__main__":
    unittest.main()
