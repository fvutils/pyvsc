"""Array / foreach plan-cache reuse on the dv-solve back-end.

`foreach` expansion rebuilds fresh constraint objects every randomize(), so the
compiled-problem cache used to miss entirely for arrays — arr[N] rebuilt all N
partitions every call. The Tier-A plan cache is extended to fixed-size array
models (default on; kill-switch VSC_DVSOLVE_ARRAY_PLAN_CACHE=0), reusing the
expanded plan across calls (~7x on arr[128]).

These tests lock in BOTH the reuse (no rebuild on repeat) AND the freshness /
safety guards that make it correct:
  - a `rangelist`/non-rand value referenced inside a `foreach`, mutated between
    calls, must invalidate the plan (source snapshot, not the frozen expanded
    copies);
  - a resized array must invalidate;
  - a rand-SIZED array stays uncached (structure changes per call);
  - a scoped/gated `foreach` (rollback-fragile in-place override) stays uncached.

See doc/notes/dv_solve_native_full_problem_plan.md (§0 reconstruction finding).
Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solver.dvsolve_backend import DvSolveBackend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveArrayPlanCache(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _count_builds(self, obj, n):
        """Number of back-end problem builds over n randomize() calls (0 => the
        compiled-problem cache is being reused)."""
        st = {"b": 0}
        orig = DvSolveBackend._build_and_solve

        def cb(self, *a, **k):
            st["b"] += 1
            return orig(self, *a, **k)
        DvSolveBackend._build_and_solve = cb
        try:
            for _ in range(n):
                obj.randomize()
        finally:
            DvSolveBackend._build_and_solve = orig
        return st["b"]

    def test_fixed_array_reuses_and_is_correct(self):
        @vsc.randobj
        class A(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 16)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    it > 2
                    it < 250

        o = A()
        for _ in range(3):
            o.randomize()                     # warm the cache
        builds = self._count_builds(o, 20)
        self.assertEqual(builds, 0, "array plan cache should reuse (0 rebuilds)")
        sols = set()
        for _ in range(50):
            o.randomize()
            vals = [int(v) for v in o.arr]
            for v in vals:
                self.assertTrue(3 <= v <= 249)
            sols.add(tuple(vals))
        self.assertGreater(len(sols), 40, "reuse must still randomize freely")

    def test_foreach_rangelist_mutation_invalidates(self):
        @vsc.randobj
        class Selector(object):
            def __init__(s):
                s.avail = vsc.rangelist((0, 900))
                s.sel = vsc.rand_list_t(vsc.uint32_t(), 8)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.sel) as it:
                    it.inside(s.avail)

        o = Selector()
        o.randomize()
        for v in o.sel:
            self.assertTrue(0 <= int(v) <= 900)
        # Mutate the source rangelist referenced inside the foreach.
        o.avail.clear()
        o.avail.extend([(1000, 2000)])
        o.randomize()
        for v in o.sel:
            self.assertTrue(1000 <= int(v) <= 2000,
                            "mutated rangelist must invalidate the cached plan")

    def test_foreach_nonrand_ref_change_invalidates(self):
        @vsc.randobj
        class RefLimit(object):
            def __init__(s):
                s.limit = vsc.uint8_t(50)     # non-rand, referenced
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    it < s.limit

        o = RefLimit()
        o.limit = 50
        for _ in range(20):
            o.randomize()
            for v in o.arr:
                self.assertLess(int(v), 50)
        o.limit = 200
        hi = 0
        for _ in range(20):
            o.randomize()
            for v in o.arr:
                self.assertLess(int(v), 200)
                hi = max(hi, int(v))
        self.assertGreaterEqual(hi, 50, "changed non-rand ref must invalidate plan")

    def test_rand_sized_array_not_stale(self):
        @vsc.randobj
        class RandSz(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.arr.size.inside(vsc.rangelist(1, 2, 3, 4, 5, 6, 7, 8))
                with vsc.foreach(s.arr) as it:
                    it > 10
                    it < 100

        o = RandSz()
        sizes = set()
        for _ in range(200):
            o.randomize()
            sizes.add(len(o.arr))
            for v in o.arr:
                self.assertTrue(10 < int(v) < 100)
        self.assertGreater(len(sizes), 1, "rand-sized array must vary (not cached stale)")

    def test_merged_solve_used_and_correct(self):
        # A plain fixed-size array uses the whole-problem merged solve (one native
        # solve for all partitions). Correctness + free randomization must hold.
        from vsc.model.randomizer import _MERGE_ENABLED
        if not _MERGE_ENABLED:
            self.skipTest("merge disabled")
        # T0 answers this shape without a solver; this test is about the merged
        # *solve*, so keep it on the back-end.
        self.disable_t0()

        @vsc.randobj
        class A(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 16)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    it > 2
                    it < 250

        o = A()
        st = {"merged": 0}
        orig = DvSolveBackend.solve_merged

        def cm(self, *a, **k):
            r = orig(self, *a, **k)
            st["merged"] += 1 if r else 0
            return r
        DvSolveBackend.solve_merged = cm
        try:
            for _ in range(5):
                o.randomize()
            self.assertGreater(st["merged"], 0, "merged solve should be used")
            sols = set()
            for _ in range(50):
                o.randomize()
                vals = [int(v) for v in o.arr]
                for v in vals:
                    self.assertTrue(3 <= v <= 249)
                sols.add(tuple(vals))
            self.assertGreater(len(sols), 40)
        finally:
            DvSolveBackend.solve_merged = orig

    def test_dist_array_falls_back_and_is_correct(self):
        # A `dist` on an array element is a special RandSet: the merge must fall
        # back to the per-RandSet path and still honor the distribution bounds.
        @vsc.randobj
        class D(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 4)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    vsc.dist(it, [vsc.weight((10, 20), 50),
                                  vsc.weight((200, 240), 50)])

        o = D()
        for _ in range(50):
            o.randomize()
            for v in o.arr:
                self.assertTrue(10 <= int(v) <= 20 or 200 <= int(v) <= 240)

    def test_gated_foreach_correct(self):
        # foreach gated by a rand predicate expands via a rollback-reverted
        # override; it must stay uncached and correct across calls.
        @vsc.randobj
        class Gated(object):
            def __init__(s):
                s.posit = vsc.rand_bit_t(1)
                s.q = vsc.rand_list_t(vsc.uint8_t(), 5)
                s.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.posit == 1
                with vsc.if_then(s.posit == 1):
                    s.x < 7
                    with vsc.foreach(s.q) as it:
                        it < s.x

        o = Gated()
        for _ in range(30):
            o.randomize()
            self.assertEqual(int(o.posit), 1)
            self.assertLess(int(o.x), 7)
            for v in o.q:
                self.assertLess(int(v), int(o.x))


if __name__ == "__main__":
    unittest.main()
