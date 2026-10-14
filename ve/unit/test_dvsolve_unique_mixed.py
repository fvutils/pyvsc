"""V7 (fallback_elimination_v2_plan.md, R8) — `unique` mixing a random-size
array with other operands is served by dv-solve, not deferred.

Only a lone random-size array was served (size-guarded pairs); any other
operand alongside it deferred with ``reason_code="array"``. Now every operand
carries an optional "inactive" guard: element k of a co-solved random-size
array is inactive when ``k >= size``, scalars and fixed-size elements never
are, and each pair is ``inactive_a || inactive_b || a != b``. Inactive
(trimmed) elements are unconstrained. Each test runs in strict mode.

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
class TestDvSolveUniqueMixed(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_randsz_and_scalar(self):
        """The probe shape (`unique_randsz_mixed`)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint8_t())
                s.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.arr.size in vsc.rangelist((1, 8))
                vsc.unique(s.arr, s.x)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(100):
                obj.randomize()
                vals = [int(v) for v in obj.arr] + [int(obj.x)]
                self.assertTrue(1 <= len(obj.arr) <= 8)
                self.assertEqual(len(set(vals)), len(vals), vals)
                sizes.add(len(obj.arr))
        self.assertGreater(len(sizes), 1, sizes)

    def test_tight_values_force_size(self):
        """Values 0..3 shared by a co-solved array and two scalars: the
        array can hold at most 2 elements, so the guards must trim it. An
        over-constrained (max-size) encoding would be UNSAT. (`size < x + 10`
        always holds; it only puts the size in the elements' RandSet, which
        otherwise solves it first and alone, then fails on sizes over 2.)"""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.randsz_list_t(vsc.uint8_t())
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.arr.size in vsc.rangelist((0, 6))
                s.arr.size < s.x + 10
                s.x < 4
                s.y < 4
                with vsc.foreach(s.arr, it=True) as it:
                    it < 4
                vsc.unique(s.arr, s.x, s.y)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(100):
                obj.randomize()
                vals = [int(v) for v in obj.arr] + [int(obj.x), int(obj.y)]
                self.assertLessEqual(len(obj.arr), 2)
                self.assertEqual(len(set(vals)), len(vals), vals)
                self.assertTrue(all(v < 4 for v in vals), vals)
                sizes.add(len(obj.arr))
        self.assertEqual(sizes, {0, 1, 2})

    def test_two_randsz_arrays(self):
        """Two co-solved random-size arrays: active elements distinct across
        both (cross-array pairs carry both arrays' guards). `it < size + 6`
        puts each size in the elements' RandSet."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.randsz_list_t(vsc.uint8_t())
                s.b = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.a.size in vsc.rangelist((1, 4))
                s.b.size in vsc.rangelist((1, 4))
                with vsc.foreach(s.a, it=True) as it:
                    it < s.a.size + 6
                with vsc.foreach(s.b, it=True) as it:
                    it < s.b.size + 6
                vsc.unique(s.a, s.b)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(100):
                obj.randomize()
                a = [int(v) for v in obj.a]
                b = [int(v) for v in obj.b]
                self.assertEqual(len(set(a + b)), len(a) + len(b), (a, b))
                self.assertTrue(all(v < len(a) + 6 for v in a), a)
                self.assertTrue(all(v < len(b) + 6 for v in b), b)
                sizes.add((len(a), len(b)))
        self.assertGreater(len(sizes), 4, sizes)

    def test_resolved_size_and_fixed_array(self):
        """Size solved in an earlier RandSet (fixed prefix), mixed with a
        fixed-size array."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.n = vsc.rand_uint8_t()
                s.arr = vsc.randsz_list_t(vsc.uint8_t())
                s.fix = vsc.rand_list_t(vsc.uint8_t(), 3)

            @vsc.constraint
            def c(s):
                s.n in vsc.rangelist((1, 5))
                s.arr.size == s.n
                vsc.solve_order(s.n, s.arr)
                vsc.unique(s.arr, s.fix)

        obj = C()
        with _strict_no_fallback():
            for _ in range(50):
                obj.randomize()
                vals = [int(v) for v in obj.arr] + [int(v) for v in obj.fix]
                self.assertEqual(len(obj.arr), int(obj.n))
                self.assertEqual(len(set(vals)), len(vals), vals)


if __name__ == "__main__":
    unittest.main()
