'''
Object-level randomization plan cache (perf §4) — correctness regression tests.

The plan cache (VSC_DVSOLVE_PLAN_CACHE) skips the per-call pre-solve passes
(VariableBoundVisitor / array expansion / RandInfoBuilder) for a static dv-solve
object and reuses a cached bound_m + RandInfo. These tests pin the two things
that matter: the value stream must be byte-identical to the non-cached path, and
the cache must invalidate on structural / value changes.

Skips when dv-solve isn't available.
'''
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as _rz
from vsc_test_case import VscTestCase


def _dvsolve_ok():
    try:
        return select_backend("dv-solve") is not None
    except Exception:
        return False


class TestPlanCache(VscTestCase):

    def setUp(self):
        super().setUp()
        if not _dvsolve_ok():
            self.skipTest("dv-solve back-end not available")
        self._saved = _rz._PLAN_CACHE_ENABLED
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        _rz._PLAN_CACHE_ENABLED = self._saved
        ctor.set_solver_backend(None)
        super().tearDown()

    def _stream(self, factory, n=120, seed=0):
        random.seed(seed)
        o = factory()
        out = []
        for _ in range(n):
            o.randomize()
            out.append(o.snapshot())
        return out

    def test_stream_identical_cache_on_vs_off(self):
        """Same seed must produce byte-identical values with the plan cache on
        and off."""
        def factory():
            @vsc.randobj
            class C(object):
                def __init__(s):
                    s.a = vsc.rand_uint16_t(); s.b = vsc.rand_uint16_t()
                    s.c = vsc.rand_uint32_t()
                @vsc.constraint
                def con(s):
                    s.a > 100; s.b > 100; s.c == s.a + s.b
                def snapshot(s):
                    return (int(s.a), int(s.b), int(s.c))
            return C()

        _rz._PLAN_CACHE_ENABLED = False
        off = self._stream(factory)
        _rz._PLAN_CACHE_ENABLED = True
        on = self._stream(factory)
        self.assertEqual(off, on)
        # And every solution is valid.
        for a, b, c in on:
            self.assertGreater(a, 100)
            self.assertGreater(b, 100)
            self.assertEqual(c, (a + b) & 0xFFFFFFFF)

    def test_invalidate_on_constraint_mode(self):
        """Disabling a constraint between randomizes must take effect (not serve
        a stale cached plan)."""
        _rz._PLAN_CACHE_ENABLED = True

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def big(s):
                s.a > 200

        o = C()
        random.seed(1)
        for _ in range(5):
            o.randomize()
            self.assertGreater(int(o.a), 200)
        o.big.constraint_mode(False)
        saw_small = False
        for _ in range(20):
            o.randomize()
            if int(o.a) <= 200:
                saw_small = True
        self.assertTrue(saw_small,
                        "constraint stayed enforced after constraint_mode(False)")

    def test_invalidate_on_nonrand_value(self):
        """Changing a referenced non-rand field's value must refresh bounds."""
        _rz._PLAN_CACHE_ENABLED = True

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.x = vsc.rand_uint16_t()
                s.lim = vsc.uint16_t(100)   # non-rand
            @vsc.constraint
            def c(s):
                s.x < s.lim

        o = C()
        random.seed(2)
        for _ in range(5):
            o.randomize()
            self.assertLess(int(o.x), 100)
        o.lim = 60000
        for _ in range(10):
            o.randomize()
            self.assertLess(int(o.x), 60000)

    def test_invalidate_on_scalar_rangelist_mutation(self):
        """A scalar `x.inside(self.rl)` (no array) must honor a mutated rangelist
        even with the plan cache on — the rangelist snapshot detects it."""
        _rz._PLAN_CACHE_ENABLED = True

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.rl = vsc.rangelist((0, 100))
                s.x = vsc.rand_uint16_t()
            @vsc.constraint
            def c(s):
                s.x.inside(s.rl)

        o = C()
        random.seed(4)
        for _ in range(8):
            o.randomize()
            self.assertTrue(0 <= int(o.x) <= 100)
        o.rl.clear(); o.rl.extend([(1000, 2000)])
        for _ in range(8):
            o.randomize()
            self.assertTrue(1000 <= int(o.x) <= 2000)

    def test_array_object_correct_with_cache(self):
        """An object with an array (foreach) is excluded from the plan cache and
        still honors a mutated rangelist."""
        _rz._PLAN_CACHE_ENABLED = True

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
        random.seed(3)
        o.randomize()
        for v in o.sel:
            self.assertTrue(0 <= int(v) <= 900)
        o.avail.clear(); o.avail.extend([(1000, 2000)])
        o.randomize()
        for v in o.sel:
            self.assertTrue(1000 <= int(v) <= 2000)


if __name__ == "__main__":
    unittest.main()
