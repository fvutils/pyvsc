"""V14 (fallback_elimination_v2_plan.md, R6) — `dist` weights above 2^32-1
are served by dv-solve, not deferred.

The native ``add_dist`` weight is a uint32, so a larger weight deferred
(``reason_code="dist"``); Boolector then crashed on it (BoolectorException).
Now all of a dist's weights are scaled by one common factor so the largest
fits, which keeps their ratios. Each test runs in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc.model.solver.dvsolve_backend import _fit_weights_u32
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


class TestFitWeights(unittest.TestCase):

    def test_fits_unchanged(self):
        ents = [_e(0, 0, 5), _e(1, 1, (1 << 32) - 1)]
        self.assertIs(_fit_weights_u32(ents), ents)

    def test_ratio_kept(self):
        out = _fit_weights_u32([_e(0, 0, 1 << 40), _e(1, 1, 3 << 40)])
        w0, w1 = out[0]["weight"], out[1]["weight"]
        self.assertLessEqual(max(w0, w1), (1 << 32) - 1)
        self.assertAlmostEqual(w1 / w0, 3.0, places=6)

    def test_zero_stays_zero_and_tiny_stays_nonzero(self):
        out = _fit_weights_u32([_e(0, 0, 0), _e(1, 1, 1), _e(2, 2, 1 << 50)])
        self.assertEqual([e["weight"] for e in out][:2], [0, 1])
        self.assertEqual(out[2]["weight"], (1 << 32) - 1)

    def test_other_fields_kept(self):
        out = _fit_weights_u32([_e(3, 9, 1 << 33, pv=False)])
        self.assertEqual((out[0]["lo"], out[0]["hi"], out[0]["is_per_value"]),
                         (3, 9, False))


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDistHugeWeight(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_probe_shape(self):
        """`dist_huge_weight`: 2^33 on [0:10] vs 1 on [20:30]."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((0, 10), 1 << 33),
                               vsc.weight((20, 30), 1)])

        obj = C()
        with _strict_no_fallback():
            for _ in range(200):
                obj.randomize()
                v = int(obj.a)
                self.assertTrue(0 <= v <= 10 or 20 <= v <= 30, v)
                # [20:30] has mass 11 / (11 * 2^33 + 11) ~ 1e-10
                self.assertLessEqual(v, 10, v)

    def test_ratio_one_to_three(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(1, 1 << 40), vsc.weight(2, 3 << 40)])

        obj = C()
        n = 2000
        hits = {1: 0, 2: 0}
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                hits[int(obj.a)] += 1
        p2 = hits[2] / n
        # 0.75 expected; 5 sigma at n=2000 is ~0.05
        self.assertTrue(0.70 < p2 < 0.80, hits)


if __name__ == "__main__":
    unittest.main()
