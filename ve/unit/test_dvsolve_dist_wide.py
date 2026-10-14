"""V15 (fallback_elimination_v2_plan.md, R2) — `dist` on a field wider than
64 bits is served by dv-solve, not deferred.

The engine's ``add_dist`` takes int64 bounds, so a wide field's `dist`
deferred (reason `dist`). A RandSet with a wide field is always served by
BV-SAT, whose samplers draw each weighted target in Python and pin it with a
wide constant (V17, V18); the engine never needs the entries. The weighting
is checked against the same `dist` on a field of <= 64 bits. Each test runs
in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase

K = 1 << 80


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
class TestDvSolveDistWide(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _draw(self, obj, n, field="a"):
        vals = []
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                vals.append(int(getattr(obj, field)))
        return vals

    def test_ranges_beyond_int64_weighted(self):
        """`[1:3] :/ 1, [K:K+5] :/ 2` on 96 bits: about 2/3 high."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(96)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((1, 3), 1),
                               vsc.weight((K, K + 5), 2)])

        vals = self._draw(C(), 600)
        self.assertTrue(all(1 <= v <= 3 or K <= v <= K + 5 for v in vals))
        hi = sum(v >= K for v in vals) / len(vals)
        self.assertTrue(0.58 < hi < 0.75, hi)
        self.assertEqual({v for v in vals if v >= K}, set(range(K, K + 6)))

    def test_per_value_weights(self):
        """`[K:K+3] := 1, K+9 := 4`: per-value mass 4 against 4."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(100)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((K, K + 3), 1, per_value=True),
                               vsc.weight(K + 9, 4)])

        vals = self._draw(C(), 600)
        top = sum(v == K + 9 for v in vals) / len(vals)
        self.assertTrue(0.4 < top < 0.6, top)

    def test_zero_weight_excluded(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(96)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((K, K + 3), 1), vsc.weight(K + 2, 0)])

        self.assertEqual(set(self._draw(C(), 300)), {K, K + 1, K + 3})

    def test_signed_wide_field(self):
        """A signed 100-bit field, one range far below zero, 1:1."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_int_t(100)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((-K - 3, -K), 1),
                               vsc.weight((K, K + 3), 1)])

        vals = self._draw(C(), 600)
        self.assertTrue(all(-K - 3 <= v <= -K or K <= v <= K + 3 for v in vals))
        neg = sum(v < 0 for v in vals) / len(vals)
        self.assertTrue(0.4 < neg < 0.6, neg)

    def test_rand_guarded_conditional(self):
        """`if (m) a dist {low} else a dist {high}`: the guard picks the
        weighting draw by draw."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.m = vsc.rand_bit_t(1)
                s.a = vsc.rand_bit_t(96)

            @vsc.constraint
            def c(s):
                with vsc.if_then(s.m == 1):
                    vsc.dist(s.a, [vsc.weight((0, 3), 1),
                                   vsc.weight((K, K + 3), 9)])
                with vsc.else_then():
                    vsc.dist(s.a, [vsc.weight((0, 3), 9),
                                   vsc.weight((K, K + 3), 1)])

        obj = C()
        pairs = []
        with _strict_no_fallback():
            for _ in range(600):
                obj.randomize()
                pairs.append((int(obj.m), int(obj.a)))
        for m in (0, 1):
            vals = [a for (mm, a) in pairs if mm == m]
            self.assertGreater(len(vals), 150)
            hi = sum(a >= K for a in vals) / len(vals)
            if m:
                self.assertGreater(hi, 0.8, hi)
            else:
                self.assertLess(hi, 0.2, hi)

    def test_with_another_constraint(self):
        """The dist and a relational constraint on the same field: every
        draw satisfies both, and the dist's weighting holds on what's left."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(96)
                s.b = vsc.rand_bit_t(96)

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((1, 3), 1),
                               vsc.weight((K, K + 5), 3)])
                s.b > s.a

        obj = C()
        with _strict_no_fallback():
            his = 0
            for _ in range(400):
                obj.randomize()
                a, b = int(obj.a), int(obj.b)
                self.assertTrue(1 <= a <= 3 or K <= a <= K + 5)
                self.assertGreater(b, a)
                his += a >= K
        self.assertTrue(0.65 < his / 400 < 0.85, his / 400)


if __name__ == "__main__":
    unittest.main()
