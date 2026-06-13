'''
Dataclass-front-end parallel of ve/unit/test_plan_cache.py.

The dc front-end reuses one composite model per instance across randomize() calls,
which is exactly the scenario the Randomizer's object-level plan cache targets — so
these correctness invariants (byte-identical stream cache on/off; invalidate on a
referenced non-rand value change) apply unchanged.

P1 subset: stream-identical and non-rand-value invalidation. The constraint_mode,
dynamic-rangelist, and array cases land with Phase 2.
'''
import random
import unittest

import vsc.dc as vdc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as _rz
from dc_test_case import DcTestCase


def _dvsolve_ok():
    try:
        return select_backend("dv-solve") is not None
    except Exception:
        return False


class TestPlanCache(DcTestCase):

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
        def factory():
            @vdc.dataclass
            class C(vdc.RandClass):
                a: vdc.u16 = vdc.rand()
                b: vdc.u16 = vdc.rand()
                c: vdc.u32 = vdc.rand()

                @vdc.constraint
                def con(s):
                    s.a > 100
                    s.b > 100
                    s.c == s.a + s.b

                def snapshot(s):
                    return (int(s.a), int(s.b), int(s.c))
            return C()

        _rz._PLAN_CACHE_ENABLED = False
        off = self._stream(factory)
        _rz._PLAN_CACHE_ENABLED = True
        on = self._stream(factory)
        self.assertEqual(off, on)
        for a, b, c in on:
            self.assertGreater(a, 100)
            self.assertGreater(b, 100)
            self.assertEqual(c, (a + b) & 0xFFFFFFFF)

    def test_invalidate_on_nonrand_value(self):
        """Changing a referenced non-rand field's value must refresh bounds."""
        _rz._PLAN_CACHE_ENABLED = True

        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u16 = vdc.rand()
            lim: vdc.u16 = vdc.field(default=100)   # non-rand

            @vdc.constraint
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
