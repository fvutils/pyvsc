"""V5 (fallback_elimination_v2_plan.md, R11) — a `sum` whose result is wider
than 63 bits is served by dv-solve, not deferred.

pyvsc sizes a sum's result to elem_w + clog2(n) so it can't overflow, so a
sum over ``uint64`` elements is 65+ bits, past the primary engine's aux
range, and the translator deferred. It now emits a balanced add tree at the
result width and serves the RandSet on BV-SAT (width-agnostic). Each test
runs in strict mode and checks the exact sum, so a truncated (wrapped) sum
fails.

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
class TestDvSolveSumWide(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _draws(self, obj, n, check):
        firsts = set()
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                vals = [int(v) for v in obj.arr]
                self.assertTrue(check(vals), (len(vals), sum(vals)))
                firsts.add(vals[0])
        self.assertGreater(len(firsts), 1)

    def test_u64_lower_bound(self):
        """The probe shape (`sum_u64_elems`)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint64_t(), 4)

            @vsc.constraint
            def c(s):
                s.arr.sum > 10

        self._draws(C(), 10, lambda v: sum(v) > 10)

    def test_u64_exact_above_2_64(self):
        """An exact total that needs the carry out of bit 63."""
        total = (1 << 65) + 5

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint64_t(), 4)

            @vsc.constraint
            def c(s):
                s.arr.sum == total

        self._draws(C(), 10, lambda v: sum(v) == total)

    def test_u64_small_bound(self):
        """A small bound: wrapping at 64 bits would admit huge elements."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint64_t(), 3)

            @vsc.constraint
            def c(s):
                s.arr.sum < 100

        self._draws(C(), 10, lambda v: sum(v) < 100)

    def test_randsz_cosolved_u64(self):
        """Size co-solved with a wide sum (size-guarded summands)."""
        total = (1 << 64) + 1

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint64_t())

            @vsc.constraint
            def c(s):
                s.arr.size in vsc.rangelist((1, 6))
                s.arr.sum == total

        self._draws(C(), 10, lambda v: 2 <= len(v) <= 6 and sum(v) == total)


if __name__ == "__main__":
    unittest.main()
