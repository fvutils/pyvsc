"""V12 (fallback_elimination_v2_plan.md, R3/R4) — several active `dist`s on
one field are served by dv-solve, not deferred.

Decision D1: match Boolector. Its swizzler picks one of the field's dists
uniformly per call and steers to that dist's weighted target. Across calls
that is the equal-probability mixture of the dists, which dv-solve emits as
one ``add_dist`` (each dist normalised to equal total mass), so the plan stays
cacheable. Every dist's ``inside`` membership stays hard (the field lies in
their intersection), and every dist's zero-weight values are excluded even
when another dist weights them. Each test runs in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import collections
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc.model.solver.dvsolve_backend import _mix_dist_entries, _dist_mass
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


def _e(lo, hi, w, pv=True):
    return {"lo": lo, "hi": hi, "weight": w, "is_per_value": pv}


class TestMixDistEntries(unittest.TestCase):

    def test_equal_mass_per_dist(self):
        a = [_e(1, 1, 9), _e(2, 2, 1)]                 # mass 10
        b = [_e(0, 9, 1), _e(20, 29, 1, pv=False)]     # mass 10 + 1 = 11
        out = _mix_dist_entries([a, b])
        self.assertEqual(_dist_mass(out[:2]), _dist_mass(out[2:]))
        self.assertEqual([e["weight"] for e in out[:2]], [99, 11])

    def test_zero_weight_and_empty_dists_dropped(self):
        out = _mix_dist_entries([[_e(1, 1, 3), _e(3, 3, 0)], [_e(5, 5, 0)]])
        self.assertEqual(out, [_e(1, 1, 3)])


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDistMulti(VscTestCase):

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

    def test_two_plain_dists(self):
        """R3 (`dist_two_plain_same_field`): the field lies in both dists'
        ranges, and both halves of the intersection are drawn."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c1(s):
                vsc.dist(s.a, [vsc.weight((0, 10), 1), vsc.weight((20, 30), 1)])

            @vsc.constraint
            def c2(s):
                vsc.dist(s.a, [vsc.weight((5, 25), 1)])

        n = 1000
        h = self._draw(C(), n)
        self.assertTrue(all(5 <= v <= 10 or 20 <= v <= 25 for v in h), h)
        lo = sum(c for v, c in h.items() if v <= 10) / n
        self.assertTrue(0.40 < lo < 0.60, lo)      # Boolector: ~0.49

    def test_two_active_conditional_dists(self):
        """R4 (`dist_two_active_conditional`): both constant guards hold."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.m = vsc.uint8_t(1)

            @vsc.constraint
            def c(s):
                with vsc.if_then(s.m == 1):
                    vsc.dist(s.a, [vsc.weight((0, 10), 1), vsc.weight((20, 30), 3)])
                with vsc.if_then(s.m > 0):
                    vsc.dist(s.a, [vsc.weight((5, 25), 1)])

        n = 1000
        h = self._draw(C(), n)
        self.assertTrue(all(5 <= v <= 10 or 20 <= v <= 25 for v in h), h)
        hi = sum(c for v, c in h.items() if v >= 20) / n
        self.assertTrue(0.52 < hi < 0.76, hi)      # Boolector ~0.60, mixture ~0.64

    def test_weights_mix_and_zero_weight_excluded(self):
        """dist A gives 3 weight 0; dist B weights 3 most heavily. 3 must
        never appear. P(1) is the mixture's 73/90 ~ 0.81 (Boolector ~0.79)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c1(s):
                vsc.dist(s.a, [vsc.weight(1, 9), vsc.weight(2, 1), vsc.weight(3, 0)])

            @vsc.constraint
            def c2(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(2, 1), vsc.weight(3, 5)])

        n = 2000
        h = self._draw(C(), n)
        self.assertEqual(set(h), {1, 2}, h)
        p1 = h[1] / n
        self.assertTrue(0.75 < p1 < 0.87, p1)

    def test_disjoint_dists_unsat(self):
        """Two dists with no common value: the memberships' intersection is
        empty, so the problem is UNSAT (as on Boolector), not deferred."""
        from vsc.model.solve_failure import SolveFailure

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(2, 1)])
                vsc.dist(s.a, [vsc.weight(3, 1), vsc.weight(4, 1)])

        with _strict_no_fallback():
            with self.assertRaises(SolveFailure):
                C().randomize()

    def test_one_of_two_conditionals_active(self):
        """Only one constant guard holds: that dist alone applies (unchanged
        behaviour), and changing the guard switches it."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.m = vsc.uint8_t(0)

            @vsc.constraint
            def c(s):
                with vsc.if_then(s.m == 0):
                    vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(2, 9)])
                with vsc.if_then(s.m == 1):
                    vsc.dist(s.a, [vsc.weight(1, 9), vsc.weight(2, 1)])

        obj = C()
        h0 = self._draw(obj, 500)
        obj.m = 1
        h1 = self._draw(obj, 500)
        self.assertGreater(h0[2], 400, h0)
        self.assertGreater(h1[1], 400, h1)

    def _draw_with(self, obj, n, *guards):
        h = collections.Counter()
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                h[(int(obj.a),) + tuple(int(getattr(obj, g)) for g in guards)] += 1
        return h

    def test_plain_with_rand_guarded(self):
        """A plain dist plus one under a rand guard (this deferred before
        V21). Guard false: the plain dist alone, uniform over 0..3. Guard
        true: the mixture, renormalised over its feasible values: the
        guarded dist excludes 3, so P(0) = 32/56 ~ 0.57."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_bit_t(1)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(0, 1), vsc.weight(1, 1),
                               vsc.weight(2, 1), vsc.weight(3, 1)])
                with vsc.if_then(s.b == 1):
                    vsc.dist(s.a, [vsc.weight(0, 6), vsc.weight(1, 1),
                                   vsc.weight(2, 1), vsc.weight(3, 0)])

        h = self._draw_with(C(), 1200, "b")
        n0 = sum(c for (a, b), c in h.items() if b == 0)
        n1 = sum(c for (a, b), c in h.items() if b == 1)
        self.assertEqual(h[(3, 1)], 0, h)
        for v in range(4):
            self.assertTrue(0.17 < h[(v, 0)] / n0 < 0.33, h)
        self.assertTrue(0.48 < h[(0, 1)] / n1 < 0.66, h)

    def test_two_rand_guarded_both_active(self):
        """Two dists under different rand guards: when both guards hold they
        apply as their mixture, P(1) = (1/2 + 3/4) / 2 = 0.625, not as the
        first branch alone (0.5)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_bit_t(1)
                s.c = vsc.rand_bit_t(1)

            @vsc.constraint
            def cc(s):
                s.a < 2
                with vsc.if_then(s.b == 1):
                    vsc.dist(s.a, [vsc.weight(0, 1), vsc.weight(1, 1)])
                with vsc.if_then(s.c == 1):
                    vsc.dist(s.a, [vsc.weight(0, 1), vsc.weight(1, 3)])

        h = self._draw_with(C(), 2000, "b", "c")
        both = h[(0, 1, 1)] + h[(1, 1, 1)]
        self.assertGreater(both, 300, h)
        self.assertTrue(0.56 < h[(1, 1, 1)] / both < 0.69, h)


if __name__ == "__main__":
    unittest.main()
