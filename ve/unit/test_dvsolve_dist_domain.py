"""V21 (fallback_elimination_v2_plan.md) — `dist` entries outside the field's
domain, and negative weights, are served by dv-solve, not deferred.

A value the field can't hold can't be chosen. The engine already drops such
a value, and clips a range to the domain, when the bound fits in int64; a
bound beyond int64 used to defer (Boolector raises on it). Now every entry is
clipped to the domain first. A negative weight counts as zero, which is what
Boolector does with it. Each test runs in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import collections
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _strict_no_fallback():
    saved = rnd._NO_FALLBACK
    rnd._NO_FALLBACK = True
    try:
        yield
    finally:
        rnd._NO_FALLBACK = saved


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDistDomain(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _draw(self, obj, n):
        h = collections.Counter()
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                h[int(obj.a)] += 1
        return h

    def test_value_beyond_int64_dropped(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint32_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(1 << 70, 5),
                               vsc.weight(2, 1)])

        n = 600
        h = self._draw(C(), n)
        self.assertEqual(set(h), {1, 2}, h)
        self.assertTrue(0.4 < h[1] / n < 0.6, h)

    def test_range_beyond_int64_clipped(self):
        """`(250, 2^70) :/ 2` keeps its weight over 250..255, so P(1) = 1/3."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight((250, 1 << 70), 2)])

        n = 900
        h = self._draw(C(), n)
        self.assertEqual(set(h) - {1}, set(range(250, 256)), h)
        self.assertTrue(0.25 < h[1] / n < 0.42, h)

    def test_signed_range_below_int64_clipped(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_int8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((-(1 << 70), -126), 1),
                               vsc.weight(5, 1)])

        n = 600
        h = self._draw(C(), n)
        self.assertEqual(set(h), {-128, -127, -126, 5}, h)
        self.assertTrue(0.4 < h[5] / n < 0.6, h)

    def test_negative_weight_is_zero(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(2, -1),
                               vsc.weight(3, 2)])

        n = 900
        h = self._draw(C(), n)
        self.assertEqual(set(h), {1, 3}, h)
        self.assertTrue(0.25 < h[1] / n < 0.42, h)


if __name__ == "__main__":
    unittest.main()
