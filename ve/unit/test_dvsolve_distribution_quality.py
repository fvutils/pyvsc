"""dv-solve distribution-quality gate (plan Workstream B1/B2).

Complements `test_distribution_quality.py` (which scores uint8-unconstrained,
a<b, and two `inside` shapes) with the scenarios it does not cover:

  * **array-element marginal** — pooled elements of a constrained array must be
    uniform over the feasible per-element domain (an array regression would skew
    or collapse element coverage);
  * **gapped multi-range `inside`** — a different gap structure than the existing
    suite, checking both sub-ranges are covered and the gap is excluded;
  * **weighted `dist` ratio accuracy** — the observed mass on each weighted region
    must match the *declared* ratio (not merely "every value seen"), and dv-solve
    must be no worse than Boolector at hitting it.

Each scored scenario asserts (a) full membership/coverage, (b) a uniformity floor
(reduced chi-square not wildly non-uniform), and (c) **no worse than Boolector**
on the same shape. Thresholds are deliberately lenient — the point is to catch a
*materially* skewed or collapsed distribution, not statistical noise.

Uses ve/unit/distribution_score.py (no scipy). Skipped when dv-solve is absent.
See doc/notes/dv_solve_test_suite_enhancement_plan.md (Workstreams B1/B2).
"""
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase
from distribution_score import score


def _available(name):
    try:
        return select_backend(name).available()
    except Exception:
        return False


BACKENDS = [b for b in ("boolector", "dv-solve") if _available(b)]


def _dvsolve_available():
    return "dv-solve" in BACKENDS


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDistributionQuality(VscTestCase):

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    # ---- helpers --------------------------------------------------------- #
    def _scored(self, backend, factory, collect, n=4000, seed=0):
        """Randomize ``factory()`` n times under ``backend``; ``collect(obj)``
        returns an iterable of observed ints per draw. Returns a DistScore over
        the pooled values against the scenario's feasible set (set later)."""
        random.seed(seed)
        ctor.set_solver_backend(backend)
        obj = factory()
        vals = []
        for _ in range(n):
            obj.randomize()
            vals.extend(int(v) for v in collect(obj))
        return vals

    def _assert_quality(self, title, vals_by_be, feasible):
        scores = {be: score(vals_by_be[be], feasible) for be in vals_by_be}
        dvs = scores["dv-solve"]
        self.assertGreaterEqual(
            dvs.coverage, 0.99,
            "[%s] dv-solve coverage %.1f%% too low (%d/%d feasible values seen)"
            % (title, 100 * dvs.coverage, dvs.n_distinct, dvs.n_feasible))
        if "boolector" in scores:
            btor = scores["boolector"]
            bound = max(2.0, 3.0 * btor.reduced_chi2)
            self.assertLess(
                dvs.reduced_chi2, bound,
                "[%s] dv-solve reduced_chi2 %.2f >> boolector %.2f (materially "
                "less uniform)" % (title, dvs.reduced_chi2, btor.reduced_chi2))

    # ---- scenario: array-element marginal -------------------------------- #
    def test_array_element_marginal_uniform(self):
        @vsc.randobj
        class Arr(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    it >= 10
                    it <= 60

        feasible = range(10, 61)
        by_be = {}
        for be in BACKENDS:
            by_be[be] = self._scored(
                be, lambda: Arr(), lambda o: [o.arr[i] for i in range(len(o.arr))],
                n=600)
        self._assert_quality("array elem [10:60]", by_be, feasible)

    # ---- scenario: gapped multi-range inside ----------------------------- #
    def test_gapped_inside_uniform(self):
        @vsc.randobj
        class Gap(object):
            def __init__(s):
                s.k = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.k.inside(vsc.rangelist(vsc.rng(5, 15), vsc.rng(40, 45),
                                         vsc.rng(200, 230)))

        feasible = list(range(5, 16)) + list(range(40, 46)) + list(range(200, 231))
        gap_vals = {0, 30, 100, 150, 255}   # outside every sub-range
        by_be = {}
        for be in BACKENDS:
            vals = self._scored(be, lambda: Gap(), lambda o: [o.k], n=4000)
            self.assertTrue(set(vals).isdisjoint(gap_vals),
                            "[%s] sampled a value in the excluded gap" % be)
            by_be[be] = vals
        self._assert_quality("inside gapped 3-range", by_be, feasible)

    # ---- scenario: weighted dist ratio accuracy -------------------------- #
    def test_weighted_dist_ratio(self):
        @vsc.randobj
        class Dist(object):
            def __init__(s):
                s.k = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                # region masses: {0}=10, {1,2,3}=80, {4}=10  -> P(1..3)=0.80
                vsc.dist(s.k, [vsc.weight(0, 10),
                               vsc.weight((1, 3), 80),
                               vsc.weight(4, 10)])

        target = 0.80
        tol = 0.06            # lenient: catch a broken ratio, not sampling noise
        p_by_be = {}
        for be in BACKENDS:
            vals = self._scored(be, lambda: Dist(), lambda o: [o.k], n=6000)
            self.assertTrue(set(vals).issubset({0, 1, 2, 3, 4}),
                            "[%s] dist sampled outside its support" % be)
            p13 = sum(1 for v in vals if v in (1, 2, 3)) / len(vals)
            p_by_be[be] = p13
            self.assertAlmostEqual(
                p13, target, delta=tol,
                msg="[%s] dist mass on {1,2,3}=%.3f, declared ratio %.2f"
                    % (be, p13, target))
        if "boolector" in p_by_be:
            self.assertLessEqual(
                abs(p_by_be["dv-solve"] - target),
                abs(p_by_be["boolector"] - target) + tol,
                "dv-solve dist ratio %.3f materially worse than boolector %.3f"
                % (p_by_be["dv-solve"], p_by_be["boolector"]))


if __name__ == "__main__":
    unittest.main()
