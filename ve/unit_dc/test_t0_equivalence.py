'''
T0 tier (no-solver direct draw) -- equivalence and eligibility.

The T0 tier answers a separable, exactly-analyzable RandSet without calling a
back-end. That is the highest-risk kind of change in this codebase, so the
primary gate here is *equivalence*: for every shape T0 claims, the values it
produces must satisfy every constraint and be distributed the same way the
solver distributes them. The kill-switch (VSC_T0 / randomizer._T0_ENABLED) is
the test methodology -- each equivalence test runs the same model both ways.

The second gate is *eligibility*: a shape T0 must not claim (coupled fields,
dist, soft, enum, randc, rand-sized arrays, non-analyzable expressions) has to
stay on the solver. Those tests assert the promotion did not happen, not merely
that the answer was right -- a wrong answer is not the only failure mode; a
right answer reached by accident is a latent one.
'''
import contextlib
import unittest
from enum import IntEnum

import vsc
import vsc.dc as vdc
import vsc.model.randomizer as rnd
import vsc.model.separability as sep
from vsc.model.solve_failure import SolveFailure

from dc_test_case import DcTestCase


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def t0(enabled):
    saved = rnd._T0_ENABLED
    rnd._T0_ENABLED = enabled
    try:
        yield
    finally:
        rnd._T0_ENABLED = saved


@contextlib.contextmanager
def promotion_spy():
    """Record, per randomize that rebuilt its plan, how many RandSets T0 took
    and how many were left for the solver."""
    log = []
    orig = sep.t0_promote

    def spy(ri):
        bounds = orig(ri)
        log.append((len(ri.t0_randset_l), len(ri.randset_l)))
        return bounds
    rnd.t0_promote = spy
    try:
        yield log
    finally:
        rnd.t0_promote = orig


@contextlib.contextmanager
def no_plan_cache():
    """Force the cold pre-solve path. The plan cache is keyed on the type's
    shared composite, so the *second* instance of a class in a process reuses
    the cached RandInfo and never re-runs the promotion -- which a probe needs
    to observe."""
    saved = rnd._PLAN_CACHE_ENABLED
    rnd._PLAN_CACHE_ENABLED = False
    try:
        yield
    finally:
        rnd._PLAN_CACHE_ENABLED = saved


def tiers(cls, n=3, **kw):
    """(t0_randsets, solver_randsets) from a cold build of `cls`.

    Forces the tier on: this file asserts what T0 does, so it must not report
    a pass merely because the ambient VSC_T0=0 turned it off.
    """
    with t0(True), no_plan_cache(), promotion_spy() as log:
        o = cls(**kw)
        for _ in range(n):
            o.randomize()
    assert log, "no plan build observed"
    return log[0]


def samples(cls, attr, n, seed=0, index=None):
    import random
    random.seed(seed)
    o = cls()
    out = []
    for _ in range(n):
        o.randomize()
        v = getattr(o, attr)
        out.append(int(v if index is None else v[index]))
    return out


def chi_square(a, b):
    """Pearson chi-square between two same-size samples, binned over their
    combined support. Returns (stat, dof)."""
    keys = sorted(set(a) | set(b))
    ca = {k: 0 for k in keys}
    cb = {k: 0 for k in keys}
    for v in a:
        ca[v] += 1
    for v in b:
        cb[v] += 1
    stat = 0.0
    dof = 0
    for k in keys:
        tot = ca[k] + cb[k]
        if tot < 5:
            continue          # pooled cell too small to be meaningful
        dof += 1
        exp = tot / 2.0
        stat += (ca[k] - exp) ** 2 / exp + (cb[k] - exp) ** 2 / exp
    return stat, max(dof - 1, 1)


def _bin(vals, nbins, lo, hi):
    w = (hi - lo + 1) / nbins
    out = [0] * nbins
    for v in vals:
        i = min(int((v - lo) / w), nbins - 1)
        out[i] += 1
    return out


# ---------------------------------------------------------------------------
# Models. Constraints are compiled from source, so they must live at module
# scope in a real file (not built inside a test method via exec).
# ---------------------------------------------------------------------------

@vdc.dataclass
class Bounded(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > 2
        self.a < 250


@vdc.dataclass
class Gapped(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a.inside(vdc.rangelist((10, 19), (200, 209)))


@vdc.dataclass
class NotEqual(vdc.RandClass):
    a: vdc.u4 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a != 5


@vdc.dataclass
class Signed(vdc.RandClass):
    a: vdc.s8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a >= -40
        self.a <= 40


@vdc.dataclass
class Wide(vdc.RandClass):
    a: vdc.u64 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > 9223372036854775808


@vdc.dataclass
class ShiftLiteral(vdc.RandClass):
    """`1 << 63` reaches the model as an ExprBinModel, not a literal -- the
    front-end does not constant-fold. T0 declines rather than reimplement the
    solver's sized-arithmetic semantics for literal expressions."""
    a: vdc.u64 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > (1 << 63)


@vdc.dataclass
class Domained(vdc.RandClass):
    a: vdc.u8 = vdc.rand(domain=[(10, 20), (100, 110)])

    @vdc.constraint
    def c(self):
        self.a < 105


@vdc.dataclass
class Arr(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=16)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


@vdc.dataclass
class Mixed(vdc.RandClass):
    """One T0-eligible field plus one coupled pair: the RandSet partition must
    split so only the eligible half is promoted."""
    k: vdc.u4 = vdc.rand()
    lo: vdc.u16 = vdc.rand()
    hi: vdc.u16 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.k <= 7
        self.lo < self.hi


@vdc.dataclass
class KnobCfg(vdc.RandClass):
    """A non-rand field read by an otherwise-T0 constraint. The domain depends
    on its value, so the plan cache must notice a change."""
    limit: vdc.u8 = 200
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.limit


@vdc.dataclass
class Coupled(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b


@vdc.dataclass
class Sum(vdc.RandClass):
    """A non-comparison expression (addition) T0 must not try to analyze."""
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a + 3 < 100


@vdc.dataclass
class Distributed(vdc.RandClass):
    k: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.dist(self.k, [vdc.weight(0, 10), vdc.weight((1, 3), 80),
                          vdc.weight(4, 10)])


@vdc.dataclass
class Soft(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.soft(self.a == 7)


class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2


@vdc.dataclass
class Enumerated(vdc.RandClass):
    c1: Color = vdc.rand()


@vdc.dataclass
class Cyclic(vdc.RandClass):
    a: vdc.u4 = vdc.randc()

    @vdc.constraint
    def c(self):
        self.a < 8


@vdc.dataclass
class Unsat(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > 200
        self.a < 100


# ---------------------------------------------------------------------------

class TestT0Eligibility(DcTestCase):
    """What T0 claims, and -- more important -- what it declines."""

    def test_bound_only_scalar_is_promoted(self):
        self.assertEqual(tiers(Bounded), (1, 0))

    def test_membership_is_promoted(self):
        self.assertEqual(tiers(Gapped), (1, 0))

    def test_inequality_is_promoted(self):
        self.assertEqual(tiers(NotEqual), (1, 0))

    def test_signed_is_promoted(self):
        self.assertEqual(tiers(Signed), (1, 0))

    def test_wide_is_promoted(self):
        # >64 bits is a back-end limitation, not a T0 one: the analysis is
        # Python-integer arithmetic over the exact interval set.
        self.assertEqual(tiers(Wide), (1, 0))

    def test_unfolded_literal_expr_stays_on_solver(self):
        self.assertEqual(tiers(ShiftLiteral), (0, 1))

    def test_declared_domain_is_promoted(self):
        self.assertEqual(tiers(Domained), (1, 0))

    def test_array_elements_are_each_promoted(self):
        self.assertEqual(tiers(Arr), (16, 0))

    def test_partition_splits_eligible_from_coupled(self):
        # `k` alone is promoted; `lo < hi` stays on the solver.
        self.assertEqual(tiers(Mixed), (1, 1))

    def test_nonrand_reference_is_promoted(self):
        self.assertEqual(tiers(KnobCfg), (1, 0))

    def test_coupled_fields_stay_on_solver(self):
        self.assertEqual(tiers(Coupled), (0, 1))

    def test_arithmetic_expr_stays_on_solver(self):
        self.assertEqual(tiers(Sum), (0, 1))

    def test_dist_stays_on_solver(self):
        self.assertEqual(tiers(Distributed), (0, 1))

    def test_soft_stays_on_solver(self):
        self.assertEqual(tiers(Soft), (0, 1))

    def test_enum_stays_on_solver(self):
        # An enum field's domain comes from its member set, not its width; T0
        # would draw values outside the enum.
        self.assertEqual(tiers(Enumerated), (0, 0))

    def test_unsat_stays_on_solver(self):
        # An empty domain is deferred so the solver reports it through the
        # normal diagnostics path rather than from the analysis.
        with t0(True), no_plan_cache(), promotion_spy() as log:
            with self.assertRaises(SolveFailure):
                Unsat().randomize()
        self.assertEqual(log[0], (0, 1))


class TestT0Equivalence(DcTestCase):
    """Values and distributions must not depend on which tier answered.

    The comparison tier is **dv-solve**, deliberately. Boolector picks values
    by swizzling a satisfying assignment, and on a multi-range domain that is
    measurably non-uniform: for `a inside [10..19],[200..209]` it never produces
    10..17 at all, and over-weights 202..209 by ~2x. That is pre-existing and
    independent of this change (it reproduces with VSC_T0=0 and with the merged
    solve disabled) -- but it means "T0 must match the solver" is only a
    meaningful equality against the tier that is itself uniform. Boolector is
    held to soundness only, in TestT0Backends.
    """

    N = 4000

    def setUp(self):
        super().setUp()
        vsc.set_solver_backend("dv-solve")

    def tearDown(self):
        vsc.set_solver_backend(None)
        super().tearDown()

    def _both(self, cls, attr, index=None, n=None):
        n = n or self.N
        with t0(True):
            on = samples(cls, attr, n, index=index)
        with t0(False):
            off = samples(cls, attr, n, index=index)
        return on, off

    def _agree(self, cls, attr, index=None, n=None):
        on, off = self._both(cls, attr, index=index, n=n)
        self.assertEqual(set(on) - set(off), set(),
                         "T0 produced values the solver never does")
        stat, dof = chi_square(on, off)
        # 3x the dof is a very loose bound (chi-square mean is dof); it catches
        # a systematically different distribution, not sampling noise.
        self.assertLess(stat, 3.0 * dof + 30.0,
                        "T0 and solver marginals differ: chi2=%.1f dof=%d"
                        % (stat, dof))
        return on, off

    def test_bounded_support_and_marginal(self):
        on, _ = self._agree(Bounded, "a")
        self.assertTrue(all(3 <= v <= 249 for v in on))
        self.assertIn(3, on)
        self.assertIn(249, on)

    def test_gapped_support_and_marginal(self):
        on, _ = self._agree(Gapped, "a")
        self.assertTrue(all(10 <= v <= 19 or 200 <= v <= 209 for v in on))
        # Both islands must be reachable, and in proportion to their size
        # (equal here): a draw that picked a range uniformly rather than a
        # value uniformly would still pass the support check.
        lo = sum(1 for v in on if v < 100)
        self.assertGreater(lo, len(on) * 0.4)
        self.assertLess(lo, len(on) * 0.6)

    def test_not_equal(self):
        on, _ = self._agree(NotEqual, "a")
        self.assertNotIn(5, on)
        self.assertEqual(set(on), set(range(16)) - {5})

    def test_signed(self):
        on, _ = self._agree(Signed, "a")
        self.assertTrue(all(-40 <= v <= 40 for v in on))
        self.assertTrue(any(v < 0 for v in on))

    def test_wide_uniform_over_upper_half(self):
        with t0(True):
            on = samples(Wide, "a", 2000)
        self.assertTrue(all(v > (1 << 63) for v in on))
        # Uniformity over a 2^63-wide domain: bin it.
        bins = _bin(on, 8, (1 << 63) + 1, (1 << 64) - 1)
        for b in bins:
            self.assertGreater(b, 2000 / 8 * 0.7, bins)
            self.assertLess(b, 2000 / 8 * 1.3, bins)

    def test_declared_domain_intersects_constraint(self):
        on, _ = self._agree(Domained, "a")
        # domain [10..20],[100..110] intersected with a < 105
        self.assertEqual(set(on), set(range(10, 21)) | set(range(100, 105)))

    def test_array_element(self):
        on, _ = self._agree(Arr, "arr", index=0, n=2000)
        self.assertTrue(all(3 <= v <= 249 for v in on))

    def test_array_elements_are_independent(self):
        # A bulk/vectorized draw that reused one value across the array would
        # pass every per-element check above.
        with t0(True):
            import random
            random.seed(0)
            o = Arr()
            same = 0
            for _ in range(200):
                o.randomize()
                if len(set(int(v) for v in o.arr)) == 1:
                    same += 1
        self.assertEqual(same, 0)

    def test_mixed_model_both_halves_correct(self):
        with t0(True):
            import random
            random.seed(0)
            o = Mixed()
            for _ in range(500):
                o.randomize()
                self.assertLessEqual(int(o.k), 7)
                self.assertLess(int(o.lo), int(o.hi))

    def test_unsat_is_reported(self):
        with t0(True):
            o = Unsat()
            with self.assertRaises(SolveFailure):
                o.randomize()

    def test_knob_change_invalidates_cached_domain(self):
        # The T0 domain is computed from the non-rand field's value and cached
        # in the plan. Changing it must re-derive, not reuse.
        with t0(True):
            o = KnobCfg()
            o.limit = 10
            for _ in range(100):
                o.randomize()
                self.assertLess(int(o.a), 10)
            o.limit = 200
            seen = set()
            for _ in range(400):
                o.randomize()
                self.assertLess(int(o.a), 200)
                seen.add(int(o.a))
            self.assertGreater(max(seen), 20,
                               "domain did not widen after the knob changed")

    def test_rand_mode_off_is_honored(self):
        with t0(True):
            o = Bounded()
            o.randomize()
            o.a = 77
            o.set_rand_mode("a", False)
            try:
                for _ in range(20):
                    o.randomize()
                    self.assertEqual(int(o.a), 77)
            finally:
                o.set_rand_mode("a", True)


class TestT0Backends(DcTestCase):
    """T0 lives above the back-end split, so it must behave identically on
    either one -- including when a back-end would never have seen the model."""

    def _backends(self):
        cur = vsc.get_solver_backend()
        out = []
        for name in ("dv-solve", "boolector"):
            try:
                vsc.set_solver_backend(name)
                out.append(name)
            except Exception:
                pass
        vsc.set_solver_backend(cur)
        return out

    def test_promotion_is_backend_independent(self):
        cur = vsc.get_solver_backend()
        try:
            for name in self._backends():
                vsc.set_solver_backend(name)
                with self.subTest(backend=name):
                    self.assertEqual(tiers(Bounded), (1, 0))
                    self.assertEqual(tiers(Gapped), (1, 0))
                    with t0(True):
                        self.assertTrue(all(
                            3 <= v <= 249
                            for v in samples(Bounded, "a", 500)))
                        self.assertTrue(all(
                            10 <= v <= 19 or 200 <= v <= 209
                            for v in samples(Gapped, "a", 500)))
        finally:
            vsc.set_solver_backend(cur)

    def test_both_backends_are_sound_without_t0(self):
        # The floor every tier must clear: whoever answers, the answer is in
        # the solution set. (Boolector's *distribution* over a multi-range
        # domain is not uniform -- see TestT0Equivalence's docstring -- which is
        # why only soundness is asserted here.)
        cur = vsc.get_solver_backend()
        try:
            for name in self._backends():
                vsc.set_solver_backend(name)
                with self.subTest(backend=name), t0(False):
                    self.assertTrue(all(
                        10 <= v <= 19 or 200 <= v <= 209
                        for v in samples(Gapped, "a", 500)))
        finally:
            vsc.set_solver_backend(cur)


class TestT0Classic(DcTestCase):
    """T0 operates on the RandInfo, below both front-ends, so the classic
    front-end gets it without any front-end change."""

    def test_classic_scalar_is_promoted(self):
        @vsc.randobj
        class A(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.a > 2
                s.a < 250

        with t0(True), no_plan_cache(), promotion_spy() as log:
            o = A()
            for _ in range(3):
                o.randomize()
                self.assertTrue(3 <= int(o.a) <= 249)
        self.assertGreater(len(log), 0)
        self.assertEqual(log[0], (1, 0))

    def test_classic_array_is_promoted(self):
        @vsc.randobj
        class A(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr) as it:
                    it > 2
                    it < 250

        with t0(True), no_plan_cache(), promotion_spy() as log:
            o = A()
            for _ in range(3):
                o.randomize()
                for v in o.arr:
                    self.assertTrue(3 <= int(v) <= 249)
        self.assertEqual(log[0], (8, 0))


if __name__ == "__main__":
    unittest.main()
