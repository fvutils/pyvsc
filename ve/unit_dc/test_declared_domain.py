"""``vdc.rand(domain=...)`` — declared domains as a property of the variable.

Phase 1 of ``doc/notes/t0_fast_tier_declared_domains_plan.md``. Before this, a
domain was desugared by ``solve_view._domain_block()`` into a synthetic
``__domain__`` block holding two ``ConstraintExprModel`` inequalities. That had
two consequences these tests lock down:

* **D-5 (live wrong answer).** ``_array_decl`` never carried ``domain`` onto the
  FieldDecl, so ``vdc.rand(size=N, domain=(lo, hi))`` was *silently ignored* and
  produced full-width elements. ``test_array_domain_applies_per_element`` is the
  regression.
* **Structural.** A domain-only field looked *constrained*, so it was dragged
  into a solve it never needed and could never take the no-solver tier that
  Phase 2 adds. ``test_domain_emits_no_constraint`` pins that a domain produces
  no entry in ``constraint_model_l`` at all.

**D-2 (dead risk, characterized not fixed).** The old code built both bounds as
``ExprLiteralModel(lo, True, 32)`` — width 32, signed, regardless of the field.
Measured before the change, all three suspect shapes (a ``u64`` domain in the
unsigned upper half, a negative ``s64`` domain below -2**31, and a ``u40`` domain
straddling 2**32) already solved correctly on both back-ends: the bin-expr
builder re-sizes the literal to the context width. So removing that code removed
dead risk, not a live bug. ``test_wide_and_signed_domains`` keeps all three
covered so the new bound-intersection path does not *introduce* the bug the old
path was merely suspected of.

The interaction rule (plan §4.1.3) is tested directly: a declared domain
**intersects** with any constraint on the field. It never widens a field, never
overrides a constraint, and an empty intersection is a normal UNSAT rather than a
silent empty draw.
"""
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc
import vsc.dc as vdc
from vsc.dc.domain import DeclaredDomain, intersect
from vsc.model.solve_failure import SolveFailure
from vsc.types import rangelist, rng


def _backends():
    """Every back-end available in this environment, for the invariants that must
    hold identically on both (domains reach Boolector by a different route than
    dv-solve: solve-time membership terms rather than ``bound_m``)."""
    from vsc.model.solver.boolector_backend import BoolectorBackend
    out = ["dv-solve"]
    if BoolectorBackend.available():
        out.append("boolector")
    return out


class TestDeclaredDomainParse(DcTestCase):
    """Normalization happens at class-definition time, so a bad spec fails there
    rather than at the first randomize()."""

    def test_inclusive_tuple(self):
        self.assertEqual(DeclaredDomain.parse((3, 250)).ranges, [[3, 250]])

    def test_range_is_half_open(self):
        """``range`` keeps Python's meaning — the same split documented for
        ``x in range(...)`` vs ``x in vdc.r[lo:hi]``."""
        self.assertEqual(DeclaredDomain.parse(range(3, 250)).ranges, [[3, 249]])
        self.assertEqual(DeclaredDomain.parse(range(8)).ranges, [[0, 7]])

    def test_single_value(self):
        self.assertEqual(DeclaredDomain.parse(7).ranges, [[7, 7]])

    def test_union_list(self):
        d = DeclaredDomain.parse([1, 2, (100, 200)])
        # 1 and 2 are adjacent and merge; the disjoint range stays separate.
        self.assertEqual(d.ranges, [[1, 2], [100, 200]])
        self.assertEqual(d.size, 103)

    def test_union_of_ranges(self):
        self.assertEqual(DeclaredDomain.parse([range(0, 8), (64, 71)]).ranges,
                         [[0, 7], [64, 71]])

    def test_overlapping_ranges_merge(self):
        self.assertEqual(DeclaredDomain.parse([(0, 10), (5, 20)]).ranges,
                         [[0, 20]])

    def test_rangelist_and_rng(self):
        self.assertEqual(DeclaredDomain.parse(rangelist(1, rng(4, 9))).ranges,
                         [[1, 1], [4, 9]])
        self.assertEqual(DeclaredDomain.parse(rng(4, 9)).ranges, [[4, 9]])

    def test_weighted_dict(self):
        d = DeclaredDomain.parse({0: 10, range(1, 4): 80, 4: 10})
        self.assertTrue(d.is_weighted)
        self.assertEqual(d.ranges, [[0, 0], [1, 3], [4, 4]])
        self.assertEqual(d.weights, [10, 80, 10])

    def test_weighted_entries_must_not_overlap(self):
        with self.assertRaises(TypeError):
            DeclaredDomain.parse({(0, 10): 1, (5, 20): 2})

    def test_weights_must_be_positive(self):
        with self.assertRaises(TypeError):
            DeclaredDomain.parse({(0, 10): 0})

    def test_reversed_interval_rejected(self):
        with self.assertRaises(TypeError):
            DeclaredDomain.parse((10, 3))

    def test_unsupported_spec_rejected(self):
        with self.assertRaises(TypeError):
            DeclaredDomain.parse("3:50")
        with self.assertRaises(TypeError):
            DeclaredDomain.parse((1, 2, 3))

    def test_parse_is_idempotent(self):
        d = DeclaredDomain.parse((3, 9))
        self.assertIs(DeclaredDomain.parse(d), d)

    def test_bad_spec_raises_at_class_definition(self):
        with self.assertRaises(TypeError):
            @vdc.dataclass
            class C(vdc.RandClass):
                a: vdc.u8 = vdc.rand(domain=(10, 3))

    def test_intersect(self):
        self.assertEqual(intersect([[0, 10], [20, 30]], [[5, 25]]),
                         [[5, 10], [20, 25]])
        self.assertEqual(intersect([[0, 10]], [[20, 30]]), [])


class TestDeclaredDomainSolve(DcTestCase):

    def test_scalar_domain_respected(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(100, 120))

        c = C()
        seen = set()
        for _ in range(200):
            c.randomize()
            self.assertTrue(100 <= c.a <= 120, "a=%d outside declared domain" % c.a)
            seen.add(c.a)
        # Not just pinned to an endpoint: the draw must cover the interval.
        self.assertGreater(len(seen), 10)

    def test_array_domain_applies_per_element(self):
        """D-5 regression: ``domain=`` on an array was silently dropped."""
        @vdc.dataclass
        class C(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=16, domain=(10, 20))

        c = C()
        seen = set()
        for _ in range(50):
            c.randomize()
            self.assertEqual(len(c.arr), 16)
            for v in c.arr:
                self.assertTrue(10 <= v <= 20, "element %d outside domain" % v)
            seen.update(c.arr)
        self.assertGreater(len(seen), 5)

    def test_gapped_domain_respected(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=[(0, 3), (200, 203)])

        c = C()
        seen = set()
        for _ in range(300):
            c.randomize()
            self.assertIn(c.a, (0, 1, 2, 3, 200, 201, 202, 203))
            seen.add(c.a)
        # Both islands must be reachable -- the gap is re-asserted, not collapsed
        # onto the enclosing range's low end.
        self.assertTrue(seen & {0, 1, 2, 3})
        self.assertTrue(seen & {200, 201, 202, 203})

    def test_range_domain_excludes_upper_endpoint(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=range(3, 6))

        c = C()
        seen = set()
        for _ in range(200):
            c.randomize()
            seen.add(c.a)
        self.assertEqual(seen, {3, 4, 5})

    def test_wide_and_signed_domains(self):
        """D-2 coverage: the three shapes the hardcoded width-32 signed literal
        was suspected of breaking. Verified correct *before* the change too."""
        LO64 = 1 << 63

        @vdc.dataclass
        class C(vdc.RandClass):
            u: vdc.u64 = vdc.rand(domain=(LO64, LO64 + 100))
            s: vdc.s64 = vdc.rand(domain=(-(1 << 40), -(1 << 40) + 100))
            w: vdc.bitv = vdc.rand(width=40, domain=((1 << 33), (1 << 33) + 50))

        c = C()
        for _ in range(40):
            c.randomize()
            self.assertTrue(LO64 <= c.u <= LO64 + 100, "u=%d" % c.u)
            self.assertTrue(-(1 << 40) <= c.s <= -(1 << 40) + 100, "s=%d" % c.s)
            self.assertTrue((1 << 33) <= c.w <= (1 << 33) + 50, "w=%d" % c.w)

    # ---- interaction rule: a domain intersects, never overrides ---- #

    def test_constraint_narrows_domain(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(10, 200))

            @vdc.constraint
            def c(self):
                self.a < 20

        c = C()
        for _ in range(100):
            c.randomize()
            self.assertTrue(10 <= c.a < 20, "a=%d" % c.a)

    def test_domain_never_widens_a_constraint(self):
        """The domain is wider than the constraint allows; the constraint wins."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(0, 255))

            @vdc.constraint
            def c(self):
                self.a in [(40, 45)]

        c = C()
        for _ in range(100):
            c.randomize()
            self.assertTrue(40 <= c.a <= 45, "a=%d" % c.a)

    def test_empty_intersection_is_unsat(self):
        """A domain disjoint from the constraint must fail the solve, not draw."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(100, 120))

            @vdc.constraint
            def c(self):
                self.a < 50

        with self.assertRaises(SolveFailure):
            C().randomize()

    def test_domain_outside_width_is_unsat(self):
        """A domain entirely above the field's width range intersects to empty."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(300, 400))

        with self.assertRaises(SolveFailure):
            C().randomize()

    def test_domain_clipped_to_width(self):
        """A domain that only *partly* overlaps the width range is clipped, not
        rejected -- intersection semantics, uniformly applied."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(250, 400))

        c = C()
        for _ in range(60):
            c.randomize()
            self.assertTrue(250 <= c.a <= 255, "a=%d" % c.a)

    def test_domain_with_cross_field_constraint(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(10, 20))
            b: vdc.u8 = vdc.rand(domain=(30, 40))

            @vdc.constraint
            def c(self):
                self.b == self.a + 25

        c = C()
        for _ in range(60):
            c.randomize()
            self.assertTrue(10 <= c.a <= 20)
            self.assertTrue(30 <= c.b <= 40)
            self.assertEqual(c.b, c.a + 25)

    # ---- structural: a domain is not a constraint ---- #

    def test_domain_emits_no_constraint(self):
        """The precondition for the Phase 2 no-solver tier: a domain-only field
        must not make the object look constrained."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=(10, 20))

        from vsc.dc import solve_view
        c = C()
        c.randomize()
        composite, field_models = solve_view.get_solve_model(c, type(c)._vsc_type_model)
        self.assertEqual([b.name for b in composite.constraint_model_l], [])
        self.assertIsNotNone(field_models["a"].declared_domain)

    def test_weighted_domain_is_recorded(self):
        """Phase 1 carries weights; Phase 5 moves them onto the fast draw. Until
        then the values must still be legal members of the domain."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain={0: 10, range(1, 4): 80, 4: 10})

        from vsc.dc import solve_view
        c = C()
        c.randomize()
        _, field_models = solve_view.get_solve_model(c, type(c)._vsc_type_model)
        dd = field_models["a"].declared_domain
        self.assertTrue(dd.is_weighted)
        self.assertEqual(dd.weights, [10, 80, 10])
        for _ in range(100):
            c.randomize()
            self.assertTrue(0 <= c.a <= 4, "a=%d" % c.a)

    # ---- rejected shapes ---- #

    def test_domain_rejected_on_enum(self):
        class E(IntEnum):
            A = 0
            B = 1

        with self.assertRaises(TypeError):
            @vdc.dataclass
            class C(vdc.RandClass):
                e: E = vdc.rand(domain=(0, 1))

    def test_domain_rejected_on_composite(self):
        @vdc.dataclass
        class Sub(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

        with self.assertRaises(TypeError):
            @vdc.dataclass
            class C(vdc.RandClass):
                s: Sub = vdc.rand(domain=(0, 1))

    # ---- both back-ends ---- #

    def test_both_backends_enforce_the_domain(self):
        """dv-solve reads the domain from ``bound_m``; Boolector gets solve-time
        membership terms. Both routes must enforce it, including the gap."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand(domain=[(0, 3), (200, 203)])
            b: vdc.u8 = vdc.rand(domain=(10, 20))

            @vdc.constraint
            def c(self):
                self.b > 15

        prev = vsc.get_solver_backend()
        try:
            for be in _backends():
                vsc.set_solver_backend(be)
                c = C()
                for _ in range(80):
                    c.randomize()
                    self.assertIn(c.a, (0, 1, 2, 3, 200, 201, 202, 203),
                                  "%s: a=%d" % (be, c.a))
                    self.assertTrue(15 < c.b <= 20, "%s: b=%d" % (be, c.b))
        finally:
            vsc.set_solver_backend(prev)
