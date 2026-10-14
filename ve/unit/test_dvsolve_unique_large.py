"""V6 (fallback_elimination_v2_plan.md, R7) — `unique` over more than 64
elements is served by dv-solve, not deferred.

The translator deferred `unique` above 64 operands (``_MAX_UNIQUE_ELEMS``)
because the pairwise-!= expansion is O(n^2). The engine takes it: 300 uint16
elements (44850 terms) solve in ~6-100 ms, where Boolector needs ~54 s per
call at 256. The cap is gone; each test runs in strict mode (no fallback).

Skipped when the dv-solve native library is unavailable.
"""
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
class TestDvSolveUniqueLarge(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _fixed(self, n, elem_t, draws, bound=None):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(elem_t(), n)

            @vsc.constraint
            def c(s):
                vsc.unique(s.arr)
                if bound is not None:
                    with vsc.foreach(s.arr) as e:
                        e < bound

        obj = C()
        firsts = set()
        with _strict_no_fallback():
            for _ in range(draws):
                obj.randomize()
                vals = [int(v) for v in obj.arr]
                self.assertEqual(len(set(vals)), n)
                if bound is not None:
                    self.assertTrue(all(v < bound for v in vals))
                firsts.add(vals[0])
        self.assertGreater(len(firsts), 1)

    def test_65_uint8(self):
        self._fixed(65, vsc.uint8_t, 20)

    def test_128_uint8_tight(self):
        """128 distinct values from 0..129: nearly a permutation."""
        self._fixed(128, vsc.uint8_t, 10, bound=130)

    def test_300_uint16(self):
        self._fixed(300, vsc.uint16_t, 5)

    def test_array_and_scalars_over_64(self):
        """Fixed-size array plus scalars, 70 operands in all."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 68)
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.unique(s.arr, s.x, s.y)

        obj = C()
        with _strict_no_fallback():
            for _ in range(10):
                obj.randomize()
                vals = [int(v) for v in obj.arr] + [int(obj.x), int(obj.y)]
                self.assertEqual(len(set(vals)), 70)

    def test_randsz_cosolved_max_100(self):
        """Co-solved random size with max size 100 (size-guarded pairs)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.l.size in vsc.rangelist((60, 100))
                with vsc.foreach(s.l, it=True) as it:
                    it < s.l.size + 50
                vsc.unique(s.l)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(10):
                obj.randomize()
                vals = [int(v) for v in obj.l]
                self.assertTrue(60 <= len(vals) <= 100, len(vals))
                self.assertEqual(len(set(vals)), len(vals))
                sizes.add(len(vals))
        self.assertGreater(len(sizes), 1)


if __name__ == "__main__":
    unittest.main()
