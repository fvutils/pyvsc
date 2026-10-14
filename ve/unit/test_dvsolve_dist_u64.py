"""V13 (fallback_elimination_v2_plan.md, R5) — `dist` ranges at or above
2^63 on a `uint64` field are served by dv-solve, not deferred.

``add_dist`` takes int64 bounds, so such a range deferred. The field's own
domain already crosses as int64 bit patterns (2^64-1 as -1), so the dist
entries now do too (_dist_patterns), and dv-solve orders an unsigned 64-bit
var's entries unsigned (dv-solve 4feafad: the picker and the BV-SAT dist
encoding used to clip them with a signed compare). The BV-SAT samplers keep
the natural values. Each test runs in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase

TOP = 1 << 63


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
class TestDvSolveDistU64(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _draw(self, obj, n):
        vals = []
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                vals.append(int(obj.a))
        return vals

    def test_upper_half_weighted(self):
        """The probe shape (`dist_u64_upper_half`), weighted 1:3."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint64_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((TOP, TOP + 9), 1),
                               vsc.weight((0, 9), 3)])

        vals = self._draw(C(), 1000)
        self.assertTrue(all(v <= 9 or TOP <= v <= TOP + 9 for v in vals))
        hi = sum(v >= TOP for v in vals) / len(vals)
        self.assertTrue(0.18 < hi < 0.32, hi)

    def test_range_straddling_2_63(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint64_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((TOP - 5, TOP + 4), 1),
                               vsc.weight((0, 9), 1)])

        vals = self._draw(C(), 600)
        self.assertTrue(all(v <= 9 or TOP - 5 <= v <= TOP + 4 for v in vals))
        mid = [v for v in vals if v > 9]
        self.assertTrue(any(v < TOP for v in mid) and any(v >= TOP for v in mid))
        self.assertTrue(0.38 < len(mid) / len(vals) < 0.62, len(mid))

    def test_upper_half_bvsat_served(self):
        """A conjunctive `if` body forces BV-SAT serving; the sampler draws
        the weighted target from the natural (unwrapped) entries."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint64_t()
                s.b = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((TOP, TOP + 9), 1),
                               vsc.weight((0, 9), 3)])
                s.b < 10
                with vsc.if_then(s.b == 3):
                    s.a != 5
                    s.a != 6

        vals = self._draw(C(), 600)
        self.assertTrue(all(v <= 9 or TOP <= v <= TOP + 9 for v in vals))
        hi = sum(v >= TOP for v in vals) / len(vals)
        self.assertTrue(0.16 < hi < 0.34, hi)


if __name__ == "__main__":
    unittest.main()
