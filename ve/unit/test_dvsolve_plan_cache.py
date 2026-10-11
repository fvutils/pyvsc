"""Retention of compiled dv-solve plans (dvsolve_backend._PLAN_CACHE).

A plan (a compiled native context) is kept on its object for reuse only once
that object has compiled the same problem twice, and the retained set is
bounded process-wide by the native memory it holds, least recently used
evicted first. riscv-dv motivated it: every instruction is a new object
randomized once through randomize_with, so unconditional retention kept a
context per instruction that could never be reused (~500 KB each).
"""
import gc
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend

from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@vsc.randobj
class Item:
    def __init__(self):
        self.a = vsc.rand_bit_t(16)
        self.b = vsc.rand_bit_t(16)

    @vsc.constraint
    def c(self):
        self.a < self.b
        self.b < 1000


@vsc.randobj
class DistItem:
    def __init__(self):
        self.a = vsc.rand_uint8_t()

    @vsc.constraint
    def d(self):
        vsc.dist(self.a, [vsc.weight(1, 80), vsc.weight(2, 20)])


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolvePlanCache(VscTestCase):

    def setUp(self):
        super().setUp()
        from vsc.model.solver import dvsolve_backend as dvb
        self.dvb = dvb
        self.disable_t0()
        ctor.set_solver_backend("dv-solve")
        gc.collect()      # earlier tests' objects: release their plans first
        saved = dvb._PLAN_CACHE.budget
        self.addCleanup(dvb.set_plan_cache_budget, saved)

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _plans(self):
        return self.dvb.plan_cache_stats()["plans"]

    def _compiles(self, fn):
        n = [0]
        orig = self.dvb._make_solve_ctx

        def spy(*a, **k):
            n[0] += 1
            return orig(*a, **k)
        self.dvb._make_solve_ctx = spy
        try:
            fn()
        finally:
            self.dvb._make_solve_ctx = orig
        return n[0]

    def test_randomize_with_retains_nothing(self):
        """Inline constraints are new objects each call: never reusable, never kept."""
        o = Item()
        before = self._plans()

        def run():
            for i in range(10):
                with o.randomize_with() as it:
                    it.a > i
                self.assertLess(int(o.a), int(o.b))
        self.assertEqual(self._compiles(run), 10)
        self.assertEqual(self._plans(), before)

    def test_merged_plan_kept_from_first_call(self):
        """Plain randomize() takes the whole-problem merged path: compiled once,
        kept within the budget, reused."""
        o = Item()
        before = self._plans()

        def run():
            for _ in range(10):
                o.randomize()
                self.assertLess(int(o.a), int(o.b))
        self.assertEqual(self._compiles(run), 1)
        self.assertEqual(self._plans(), before + 1)

    def test_per_randset_plan_kept_from_second_compile(self):
        """A per-RandSet plan (a dist isn't merged) is kept once its problem recurs."""
        o = DistItem()
        before = self._plans()

        def run():
            for _ in range(10):
                o.randomize()
                self.assertIn(int(o.a), (1, 2))
        self.assertEqual(self._compiles(run), 2)
        self.assertEqual(self._plans(), before + 1)

    def test_budget_evicts_least_recent(self):
        cache = self.dvb._PLAN_CACHE
        objs = [Item() for _ in range(6)]
        for o in objs:                       # retain one plan per object
            o.randomize()
            o.randomize()
        per_plan = max(1, cache.bytes // max(1, self._plans()))
        ev0 = cache.evictions
        self.dvb.set_plan_cache_budget(per_plan * 2)   # room for about two plans
        self.assertLessEqual(cache.bytes, cache.budget)
        for o in objs:
            o.randomize()
            o.randomize()
        self.assertLessEqual(cache.bytes, cache.budget)
        self.assertGreater(cache.evictions, ev0)
        for o in objs:                       # evicted objects still solve correctly
            for _ in range(3):
                o.randomize()
                self.assertLess(int(o.a), int(o.b))

    def test_zero_budget_retains_nothing(self):
        self.dvb.set_plan_cache_budget(0)
        o = Item()
        before = self._plans()
        self.assertEqual(self._compiles(lambda: [o.randomize() for _ in range(5)]), 5)
        self.assertEqual(self._plans(), before)

    def test_collected_object_releases_plan(self):
        o = Item()
        o.randomize()
        o.randomize()
        held = self.dvb.plan_cache_stats()["bytes"]
        self.assertGreater(held, 0)
        del o
        gc.collect()
        self.assertLess(self.dvb.plan_cache_stats()["bytes"], held)


if __name__ == "__main__":
    unittest.main()
