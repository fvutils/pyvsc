"""Phase B — native ``dist`` on the dv-solve back-end.

These tests assert that ``dist`` constraints are handled *natively* by dv-solve
(via the C ``add_dist`` primitive), not silently served by the Boolector
fallback. Each randomization runs under a "no-fallback" guard that makes any
fallback to Boolector raise, so a regression that re-introduces the defer fails
loudly here rather than passing quietly through the oracle.

Coverage:
  * T-B1 native domain restriction (gapped ranges), no fallback
  * T-B2 weighted bias (per-value ``:=``)
  * T-B3 per-range divided (``:/``)
  * T-B4 zero-weight exclusion (static + dynamic)
  * T-B5 ``:=`` vs ``:/`` distinction (the B-2a front-end flag)
  * T-B6 per-seed determinism
  * T-B7 fallback safety — dist + unsupported construct still weighted via Boolector
  * T-B8 plan-cache (compile-once / rebuild-on-change)
  * T-B9 distribution parity vs Boolector
  * B-6 strict no-fallback: native dist never defers; §5 shapes do

See doc/notes/dv_solve_phaseB_dist_plan.md. Skipped when the dv-solve native
library is unavailable.
"""
import random
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase

from distribution_score import score


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _no_fallback():
    """Make any fall-through to the Boolector back-end raise, so a dist that is
    *not* handled natively by dv-solve fails the test instead of being served
    by the oracle."""
    import vsc.model.solver.boolector_backend as bb
    orig = bb.BoolectorBackend.solve_randset

    def _raise(self, rs, *a, **k):
        raise AssertionError(
            "dv-solve fell back to Boolector for a RandSet (dist not native?)")

    bb.BoolectorBackend.solve_randset = _raise
    try:
        yield
    finally:
        bb.BoolectorBackend.solve_randset = orig


@contextmanager
def _strict_no_fallback():
    """Enable the production VSC_DVSOLVE_NO_FALLBACK strict mode (Phase 0): the
    Randomizer re-raises BackendIncomplete instead of falling back, carrying the
    reason_code. Lets a test assert *which* dist shapes still defer."""
    import vsc.model.randomizer as rnd
    saved = rnd._NO_FALLBACK
    rnd._NO_FALLBACK = True
    try:
        yield
    finally:
        rnd._NO_FALLBACK = saved


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDistNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _draw(self, obj, field, n=1000, seed=0):
        random.seed(seed)
        vals = []
        with _no_fallback():
            for _ in range(n):
                obj.randomize()
                vals.append(int(getattr(obj, field)))
        return vals

    # ------------------------------------------------------------------ #
    # T-B1 — native domain restriction over gapped ranges                  #
    # ------------------------------------------------------------------ #
    def test_tb1_domain_restriction(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight((1, 3), 1), vsc.weight((5, 6), 1)])

        feasible = {1, 2, 3, 5, 6}
        vals = self._draw(C(), "a", n=600)
        self.assertTrue(set(vals) <= feasible,
                        "out-of-domain values: %s" % (set(vals) - feasible))
        # Uniform-ish coverage over the feasible set (equal-weight ranges).
        sc = score(vals, feasible)
        self.assertEqual(sc.n_distinct, len(feasible),
                         "did not cover the feasible set: %s" % sc)

    # ------------------------------------------------------------------ #
    # T-B2 — weighted per-value bias                                       #
    # ------------------------------------------------------------------ #
    def test_tb2_weighted_bias(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(0, 1), vsc.weight(255, 3)])

        vals = self._draw(C(), "a", n=2000)
        self.assertTrue(set(vals) <= {0, 255})
        ratio = sum(1 for v in vals if v == 255) / len(vals)
        # Expect ~0.75 (3/(1+3)); generous tolerance for sampling noise.
        self.assertGreater(ratio, 0.65)
        self.assertLess(ratio, 0.85)

    # ------------------------------------------------------------------ #
    # T-B3 — per-range divided (:/)                                        #
    # ------------------------------------------------------------------ #
    def test_tb3_range_divided(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                # default range form is :/ (per-range weight)
                vsc.dist(s.a, [vsc.weight((0, 9), 1), vsc.weight((10, 19), 3)])

        vals = self._draw(C(), "a", n=2000)
        self.assertTrue(all(0 <= v <= 19 for v in vals))
        ratio = sum(1 for v in vals if v >= 10) / len(vals)
        # [10:19] carries 3/4 of the weight regardless of range width (:/).
        self.assertGreater(ratio, 0.65)
        self.assertLess(ratio, 0.85)

    # ------------------------------------------------------------------ #
    # T-B4 — zero-weight exclusion (static + dynamic)                      #
    # ------------------------------------------------------------------ #
    def test_tb4_zero_weight_static(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(0, 0), vsc.weight(1, 1)])

        vals = self._draw(C(), "a", n=200)
        self.assertEqual(set(vals), {1}, "zero-weight value 0 was selected")

    def test_tb4_zero_weight_dynamic(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.en_one = vsc.uint8_t()
                s.en_two = vsc.uint8_t()
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(1, s.en_one), vsc.weight(2, s.en_two)])

        c = C()
        c.en_one, c.en_two = 1, 0
        self.assertEqual(set(self._draw(c, "a", n=50)), {1})
        c.en_one, c.en_two = 0, 1
        self.assertEqual(set(self._draw(c, "a", n=50)), {2})
        c.en_one, c.en_two = 1, 1
        self.assertTrue(set(self._draw(c, "a", n=50)) <= {1, 2})

    # ------------------------------------------------------------------ #
    # T-B5 — := vs :/ distinction (B-2a front-end flag)                    #
    # ------------------------------------------------------------------ #
    def test_tb5_per_value_vs_per_range(self):
        # Two ranges of very different width carrying equal *entry* weight.
        # Under :/ (per-range) each range gets ~50% of the mass regardless of
        # width. Under := (per-value) the wide range gets proportionally more.
        def make(per_value):
            @vsc.randobj
            class C(object):
                def __init__(s):
                    s.a = vsc.rand_uint8_t()
                @vsc.constraint
                def d(s):
                    vsc.dist(s.a, [
                        vsc.weight((0, 0), 1, per_value=per_value),
                        vsc.weight((10, 99), 1, per_value=per_value)])
            return C()

        per_range = self._draw(make(False), "a", n=2000, seed=1)
        per_value = self._draw(make(True), "a", n=2000, seed=1)

        pr_wide = sum(1 for v in per_range if v >= 10) / len(per_range)
        pv_wide = sum(1 for v in per_value if v >= 10) / len(per_value)

        # :/ splits the mass ~50/50 between the two entries (range width
        # ignored); := weights by population so the 90-value range dominates.
        self.assertLess(pr_wide, 0.70,
                        ":/ should give the wide range ~half the mass, got %.2f" % pr_wide)
        self.assertGreater(pv_wide, 0.90,
                           ":= should weight by value count, got %.2f" % pv_wide)
        self.assertGreater(pv_wide, pr_wide + 0.20,
                           ":= and :/ should differ materially")

    # ------------------------------------------------------------------ #
    # T-B8 — plan-cache: compile-once for static dist, rebuild on change   #
    # ------------------------------------------------------------------ #
    def _count_builds(self, obj, field, n, mutate=None):
        """Randomize ``obj`` n times counting how many times the dv-solve
        back-end actually (re)builds+compiles a problem. ``mutate(obj, i)`` runs
        before each randomize."""
        import vsc.model.solver.dvsolve_backend as dv
        builds = {"n": 0}
        orig = dv.DvSolveBackend._build_and_solve

        def counting(self_, *a, **k):
            builds["n"] += 1
            return orig(self_, *a, **k)

        dv.DvSolveBackend._build_and_solve = counting
        try:
            with _no_fallback():
                for i in range(n):
                    if mutate is not None:
                        mutate(obj, i)
                    obj.randomize()
        finally:
            dv.DvSolveBackend._build_and_solve = orig
        return builds["n"]

    def test_tb8_plan_cache_static(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(1, 80), vsc.weight(2, 20)])

        # A static dist compiles once, then reuses the cached plan/problem.
        builds = self._count_builds(C(), "a", n=8)
        self.assertEqual(builds, 1,
                         "static dist should compile once, rebuilt %d times" % builds)

    def test_tb8_plan_cache_rebuild_on_weight_change(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.w = vsc.uint8_t()
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                # dynamic weight: changing s.w must invalidate the cached plan
                vsc.dist(s.a, [vsc.weight(1, s.w), vsc.weight(2, 1)])

        c = C()
        c.w = 1

        # Alternate the weight every other call: each change forces a rebuild,
        # an unchanged call reuses. 8 calls toggling -> several rebuilds, and
        # crucially never a *stale* result.
        def mutate(o, i):
            o.w = 1 if (i % 2 == 0) else 5

        seen = []
        import vsc.model.solver.dvsolve_backend as dv
        orig = dv.DvSolveBackend._build_and_solve
        builds = {"n": 0}
        dv.DvSolveBackend._build_and_solve = lambda s, *a, **k: (
            builds.__setitem__("n", builds["n"] + 1), orig(s, *a, **k))[1]
        try:
            with _no_fallback():
                for i in range(8):
                    mutate(c, i)
                    c.randomize()
                    seen.append(int(c.a))
        finally:
            dv.DvSolveBackend._build_and_solve = orig

        # Weight toggles between two distinct configs -> at least 2 rebuilds
        # (more than the 1 a fully-static object would need), proving the plan
        # is invalidated on a (dynamic) weight change.
        self.assertGreaterEqual(builds["n"], 2,
                                "dynamic weight change did not invalidate the plan")
        self.assertTrue(set(seen) <= {1, 2})

    # ------------------------------------------------------------------ #
    # T-B6 — per-seed determinism                                          #
    # ------------------------------------------------------------------ #
    def test_tb6_determinism(self):
        def make():
            @vsc.randobj
            class C(object):
                def __init__(s):
                    s.a = vsc.rand_uint8_t()
                @vsc.constraint
                def d(s):
                    vsc.dist(s.a, [vsc.weight((10, 15), 80),
                                   vsc.weight((20, 30), 40),
                                   vsc.weight((80, 100), 10)])
            return C()

        run1 = self._draw(make(), "a", n=200, seed=12345)
        run2 = self._draw(make(), "a", n=200, seed=12345)
        self.assertEqual(run1, run2, "dist value stream is not reproducible per seed")

    # ------------------------------------------------------------------ #
    # B-6 — strict no-fallback: native dist never defers; §5 shapes do     #
    # ------------------------------------------------------------------ #
    def test_b6_native_dist_no_fallback(self):
        """Under VSC_DVSOLVE_NO_FALLBACK the common dist shapes (single
        unconditional value/range/zero-weight, per-value or per-range) must
        solve natively with no deferral."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [
                    vsc.weight(0, 0),                       # zero-weight exclude
                    vsc.weight((1, 8), 60),                 # :/ range
                    vsc.weight((200, 255), 7, per_value=True)])  # := range

        with _strict_no_fallback():
            c = C()
            for _ in range(50):
                c.randomize()
                self.assertTrue(1 <= int(c.a) <= 8 or 200 <= int(c.a) <= 255)

    def test_b6_deferrals_carry_dist_reason(self):
        """The §5 dist shapes that genuinely can't be native (multiple
        *unconditional* dists per field, >64-bit) defer with reason_code 'dist'
        under strict mode — the enumerated, expected burn-down residue.
        (Conditional dist is now served natively — see
        test_conditional_dist_native.)"""
        from vsc.model.solver.backend import BackendIncomplete

        def expect_defer(make, label):
            with _strict_no_fallback():
                try:
                    make().randomize()
                except BackendIncomplete as e:
                    self.assertEqual(getattr(e, "reason_code", None), "dist",
                                     "%s: reason=%r" % (label, getattr(e, "reason_code", None)))
                    return
            self.fail("%s: expected a dist deferral, got none" % label)

        @vsc.randobj
        class MultiDist(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight(1, 1), vsc.weight(2, 1)])
                vsc.dist(s.a, [vsc.weight(3, 1), vsc.weight(4, 1)])
        expect_defer(lambda: MultiDist(), "multiple dist on one field")

        @vsc.randobj
        class WideDist(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(72)
            @vsc.constraint
            def d(s):
                vsc.dist(s.a, [vsc.weight((0, 9), 1), vsc.weight((10, 19), 3)])
        expect_defer(lambda: WideDist(), ">64-bit dist")

    # ------------------------------------------------------------------ #
    # B-F2 — conditional dist (if/else) is served natively                 #
    # ------------------------------------------------------------------ #
    def test_conditional_dist_native(self):
        """A conditional dist (``with if_then(b==1): dist(a, …)``) is served
        natively, no fallback. When the guard is a solve-time constant (non-rand
        ``b``) the active branch's native weighting is honored; the inactive
        branch contributes nothing. Run under strict no-fallback so a regression
        to deferral fails loudly."""
        @vsc.randobj
        class Cond(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.uint8_t()
            @vsc.constraint
            def dc(s):
                with vsc.if_then(s.b == 1):
                    vsc.dist(s.a, [vsc.weight((10, 15), 80),
                                   vsc.weight((80, 100), 10)])
                with vsc.else_then:
                    vsc.dist(s.a, [vsc.weight((10, 15), 10),
                                   vsc.weight((80, 100), 80)])

        def run(bval, n=400):
            c = Cond(); c.b = bval
            lo = hi = 0
            with _strict_no_fallback():
                for _ in range(n):
                    c.randomize()
                    a = int(c.a)
                    self.assertTrue(10 <= a <= 15 or 80 <= a <= 100,
                                    "conditional dist membership violated: %d" % a)
                    if a <= 15:
                        lo += 1
                    else:
                        hi += 1
            return lo, hi

        lo1, hi1 = run(1)
        self.assertGreater(lo1, hi1,
                           "b==1 should weight the low range heavier: lo=%d hi=%d"
                           % (lo1, hi1))
        lo0, hi0 = run(0)
        self.assertGreater(hi0, lo0,
                           "b==0 should weight the high range heavier: lo=%d hi=%d"
                           % (lo0, hi0))

    def test_conditional_dist_rand_guard_native(self):
        """A conditional dist whose guard is itself *rand* is served natively too
        (no fallback): the guarded membership is always honored. The conditional
        *weighting* is not asserted (the documented reduced-distribution guarantee
        for rand-guarded dist — the picker covers the feasible union uniformly)."""
        @vsc.randobj
        class CondRand(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_bit_t(1)
            @vsc.constraint
            def dc(s):
                with vsc.if_then(s.b == 1):
                    vsc.dist(s.a, [vsc.weight((10, 15), 80),
                                   vsc.weight((80, 100), 10)])
                with vsc.else_then:
                    vsc.dist(s.a, [vsc.weight((10, 15), 10),
                                   vsc.weight((80, 100), 80)])

        c = CondRand()
        with _strict_no_fallback():
            for _ in range(200):
                c.randomize()
                a = int(c.a)
                self.assertTrue(10 <= a <= 15 or 80 <= a <= 100,
                                "rand-guard conditional dist membership: %d" % a)

    # ------------------------------------------------------------------ #
    # EF-1b — dist weighting honored when the RandSet force-serves via      #
    #         BV-SAT (a dist combined with a conjunctive-body implication,  #
    #         which routes off the primary's add_dist value picker).        #
    # ------------------------------------------------------------------ #
    def test_ef1b_dist_with_conjunctive_implies_keeps_weighting(self):
        """A dist field in a RandSet that also carries a conjunctive-body
        implication (``with implies(g): a==0; b==0``) force-serves via the
        complete BV-SAT engine (the primary's disjunction propagation is unsound
        over the AND-leaf'd ``(!g) || (a==0 && b==0)``). The BV-SAT engine ignores
        ``add_dist``, so without the EF-1b weighted assume-then-assert pre-stage
        (``bvsat_sampler.sample_dist``) the 99999:1 weighting washes out to ~50/50
        (the ``test_dist_multiple_dists_in_randset`` regression). Assert: served
        natively (no fallback) AND the weighting is honored on every dist field."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t()
                s.b = vsc.rand_bit_t()
                s.en = vsc.rand_bit_t()
            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight(0, 1), vsc.weight(1, 99999)])
                vsc.dist(s.b, [vsc.weight(0, 1), vsc.weight(1, 99999)])
                with vsc.implies(s.en == 0):   # conjunctive body -> BV-SAT route
                    s.a == 0
                    s.b == 0

        ones = [0, 0]
        n = 200
        with _strict_no_fallback():            # serve-SAT auto-activates (no net)
            c = C()
            for _ in range(n):
                with c.randomize_with() as it:
                    it.en == 1                 # guard false -> a,b free, weighted
                ones[0] += int(c.a)
                ones[1] += int(c.b)
        # ~99.999% ones expected; uniform (the bug) would land ~50%. A generous
        # floor (85%) locks the weighting without flaking on the rare 0 draw.
        for i, k in enumerate(ones):
            self.assertGreater(
                k, int(0.85 * n),
                "dist weighting lost on field %s (force-served via BV-SAT): "
                "%d/%d ones — expected ~%d" % ("ab"[i], k, n, n))

    # ------------------------------------------------------------------ #
    # T-B7 — fallback safety: dist + unsupported construct stays weighted  #
    # ------------------------------------------------------------------ #
    def test_tb7_fallback_keeps_dist_weighting(self):
        """When a dist RandSet also carries a construct dv-solve can't handle, the
        whole RandSet falls back to Boolector. The dist's membership + weighting
        must survive the native-path de-dup (B-4): Boolector serves it via the
        swizzler's weight_list. Asserts in-domain + the requested 3:1 bias. (No
        no-fallback guard — this case *should* fall back.)

        NOTE: the trigger must be a construct dv-solve still defers. Phase C keeps
        making array constructs native (fixed-size ``sum``/``product``/``unique``
        all became native), so this uses ``a inside arr`` (membership over an
        array's elements), which stays deferred. When that eventually lands,
        repoint this at the next still-deferred construct — or retire the test once
        Boolector is removed (Phase E)."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 3)
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a.inside(s.arr)                      # 'in' over array -> defers
                vsc.dist(s.a, [vsc.weight((10, 20), 1),
                               vsc.weight((200, 250), 3)])

        c = C()
        random.seed(0)
        vals = []
        for _ in range(300):
            c.randomize()
            v = int(c.a)
            self.assertIn(v, [int(x) for x in c.arr],
                          "fallback dropped 'a inside arr': a=%d arr=%s" %
                          (v, [int(x) for x in c.arr]))
            self.assertTrue(10 <= v <= 20 or 200 <= v <= 250,
                            "fallback dropped dist membership: a=%d" % v)
            vals.append(v)
        hi = sum(1 for v in vals if v >= 200) / len(vals)
        self.assertGreater(hi, 0.6,
                           "fallback dropped dist weighting (P(high)=%.2f)" % hi)

    # ------------------------------------------------------------------ #
    # T-B9 — distribution parity: native dv-solve vs Boolector             #
    # ------------------------------------------------------------------ #
    def test_tb9_distribution_parity_vs_boolector(self):
        """Native dv-solve dist must be no worse than Boolector at realizing the
        requested weights. Compare per-range mass on the same weighted dist; both
        should land near the analytic target and within tolerance of each other."""
        def make():
            @vsc.randobj
            class C(object):
                def __init__(s):
                    s.a = vsc.rand_uint8_t()
                @vsc.constraint
                def d(s):
                    vsc.dist(s.a, [vsc.weight((0, 9), 1),
                                   vsc.weight((10, 19), 3)])   # 1:3 -> P(high)=0.75
            return C()

        def run(backend, n=3000):
            ctor.set_solver_backend(backend)
            random.seed(7)
            obj = make()
            hi = 0
            for _ in range(n):
                obj.randomize()
                v = int(obj.a)
                self.assertTrue(0 <= v <= 19)
                hi += (v >= 10)
            return hi / n

        try:
            dv_hi = run("dv-solve")
            bt_hi = run("boolector")
        finally:
            ctor.set_solver_backend("dv-solve")

        # Both near the 0.75 target...
        self.assertAlmostEqual(dv_hi, 0.75, delta=0.10,
                               msg="dv-solve P(high)=%.3f" % dv_hi)
        self.assertAlmostEqual(bt_hi, 0.75, delta=0.10,
                               msg="boolector P(high)=%.3f" % bt_hi)
        # ...and dv-solve is no worse than Boolector (within sampling noise).
        self.assertLess(abs(dv_hi - 0.75), abs(bt_hi - 0.75) + 0.08,
                        "dv-solve %.3f materially worse than boolector %.3f"
                        % (dv_hi, bt_hi))


if __name__ == "__main__":
    unittest.main()
