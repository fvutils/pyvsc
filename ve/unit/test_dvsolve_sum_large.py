"""V4 (fallback_elimination_v2_plan.md, R9/R10) — `sum` over more than 64
elements is served by dv-solve, not deferred.

The translator deferred a sum over more than 64 elements (``_MAX_SUM_VARS``),
fixed-size and size-guarded alike, because the engine's sum propagator held
at most 64 summands. dv-solve 76546ea sizes the propagator to its summands,
so the cap is gone (`sum_100`: ~0.1 ms, Boolector 44 ms). Each test runs in
strict mode.

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
class TestDvSolveSumLarge(VscTestCase):

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

    def test_sum_100_bound(self):
        """The probe shape (`sum_100`)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 100)

            @vsc.constraint
            def c(s):
                s.arr.sum < 5000

        self._draws(C(), 20, lambda v: sum(v) < 5000)

    def test_sum_250_exact(self):
        """An exact total over 250 bounded elements."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 250)

            @vsc.constraint
            def c(s):
                s.arr.sum == 750
                with vsc.foreach(s.arr) as e:
                    e < 6

        self._draws(C(), 10, lambda v: sum(v) == 750 and max(v) < 6)

    def test_randsz_resolved_max_100(self):
        """The probe shape (`sum_randsz_max100`): size solved first."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.arr.size in vsc.rangelist((90, 100))
                s.arr.sum < 5000

        self._draws(C(), 20, lambda v: 90 <= len(v) <= 100 and sum(v) < 5000)

    def test_randsz_cosolved_max_100(self):
        """Size co-solved with the sum (size-guarded summands)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.arr.size in vsc.rangelist((70, 100))
                s.arr.sum == 2 * s.arr.size
                with vsc.foreach(s.arr) as e:
                    e < 5

        self._draws(C(), 20, lambda v: 70 <= len(v) <= 100
                    and sum(v) == 2 * len(v) and max(v) < 5)


if __name__ == "__main__":
    unittest.main()
