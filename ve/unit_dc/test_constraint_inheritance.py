'''
Dataclass-front-end adaptation of the Verilator constraint-inheritance corpus:
t_constraint_inheritance.v, t_constraint_inheritance_with.v,
t_randomize_derived_this.v, and t_randc_extends.v.

Exercises the SV/PSS constraint-inheritance semantics on the dc front-end:
  - rand fields and @vdc.constraint blocks ACCUMULATE down the class hierarchy
    (a base constraint applies to every descendant);
  - a same-named @vdc.constraint in a subclass REPLACES the base one (override,
    not conjunction);
  - an empty subclass inherits every field and constraint of its ancestors;
  - hierarchical constraints on a nested rand object survive inheritance, and a
    parent hard constraint overrides a child soft;
  - inline ``randomize_with`` constraints reference inherited fields;
  - an inherited randc field still cycles.

Every RandClass level that ADDS fields must be decorated with @vdc.dataclass —
forgetting it is caught with an actionable error (test_undecorated_level_errors).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


# --- t_constraint_inheritance: field + constraint accumulation --------------
@vdc.dataclass
class B(vdc.RandClass):
    x: vdc.s32 = vdc.rand()

    @vdc.constraint
    def x_gt_0(self):
        self.x > 0


@vdc.dataclass
class C(B):                       # inherits x + x_gt_0; adds y
    y: vdc.s32 = vdc.rand()


@vdc.dataclass
class D(C):                       # inherits x,y,x_gt_0; adds x < y
    @vdc.constraint
    def x_lt_y(self):
        self.x < self.y


@vdc.dataclass
class E(C):                       # inherits x,y,x_gt_0; adds x<20, x>y
    @vdc.constraint
    def x_lt_20(self):
        self.x < 20

    @vdc.constraint
    def x_gt_y(self):
        self.x > self.y


class TestConstraintInheritance(DcTestCase):

    def _randomize_varies(self, obj, pred, probe, n=20):
        """Assert ``pred`` holds every draw and ``probe(obj)`` takes >1 value."""
        seen = set()
        for _ in range(n):
            obj.randomize()
            self.assertTrue(pred(obj),
                            "constraint violated: %s" % probe(obj).__repr__())
            seen.add(probe(obj))
        self.assertGreater(len(seen), 1, "field never varied")

    def test_base_constraint(self):
        # B: only x, only x > 0.
        self._randomize_varies(B(), lambda o: o.x > 0, lambda o: int(o.x))

    def test_inherited_constraint_plus_new_field(self):
        # C inherits x_gt_0 and adds an unconstrained y — both range, x stays > 0.
        c = C()
        seen_y = set()
        for _ in range(20):
            c.randomize()
            self.assertGreater(c.x, 0)
            seen_y.add(int(c.y))
        self.assertGreater(len(seen_y), 1)

    def test_derived_adds_constraint(self):
        # D: inherited x>0 AND its own x<y.
        self._randomize_varies(
            D(), lambda o: o.x > 0 and o.x < o.y, lambda o: int(o.x))

    def test_multi_constraint_derived(self):
        # E: inherited x>0 AND own x<20 AND own x>y.
        self._randomize_varies(
            E(), lambda o: 0 < o.x < 20 and o.x > o.y, lambda o: int(o.x))

    def test_constraints_accumulate_in_type_model(self):
        # The inherited base constraint is present in the derived type model.
        names = {c.name for c in E()._get_type_model().constraints}
        self.assertEqual(names, {"x_gt_0", "x_lt_20", "x_gt_y"})
        self.assertEqual([f.name for f in C()._get_type_model().fields],
                         ["x", "y"])


# --- t_constraint_inheritance_with: inline `with` + inheritance -------------
@vdc.dataclass
class WA(vdc.RandClass):
    x: vdc.s32 = vdc.rand()


@vdc.dataclass
class WB(WA):
    @vdc.constraint
    def x_gt_0(self):
        self.x > 0


@vdc.dataclass
class WC(WB):
    y: vdc.s32 = vdc.rand()


@vdc.dataclass
class WD(WC):
    z: vdc.s32 = vdc.rand()

    @vdc.constraint
    def x_lt_y(self):
        self.x < self.y


@vdc.dataclass
class WE(WC):
    @vdc.constraint
    def x_gt_y(self):
        self.x > self.y


class TestConstraintInheritanceWith(DcTestCase):

    def test_inline_with_on_base_field(self):
        # WB: inherited x>0, inline x<100 references the (grand)base field x.
        b = WB()
        seen = set()
        for _ in range(20):
            with b.randomize_with() as it:
                it.x < 100
            self.assertTrue(0 < b.x < 100)
            seen.add(int(b.x))
        self.assertGreater(len(seen), 1)

    def test_inline_with_multi_level_fields(self):
        # WD: inline references own z and inherited x,y; base+own hard hold too.
        d = WD()
        seen = set()
        for _ in range(20):
            with d.randomize_with() as it:
                it.z > it.x
                it.z < it.y
            self.assertTrue(d.x > 0 and d.x < d.y)
            self.assertTrue(d.x < d.z < d.y)
            seen.add(int(d.x))
        self.assertGreater(len(seen), 1)

    def test_inline_with_inside_plus_inherited(self):
        # WE: inline x inside [10:20] combined with inherited x>0 and own x>y.
        e = WE()
        for _ in range(20):
            with e.randomize_with() as it:
                it.x in vdc.rangelist((10, 20))
            self.assertTrue(10 <= e.x <= 20 and e.x > 0 and e.x > e.y)


# --- t_randomize_derived_this: empty subclasses inherit everything ----------
@vdc.dataclass
class sub_cfg(vdc.RandClass):
    enabled: vdc.u1 = vdc.rand()

    @vdc.constraint
    def defaults(self):
        vdc.soft(self.enabled == 0)


@vdc.dataclass
class base_c(vdc.RandClass):
    cfg: sub_cfg = vdc.rand()
    watchdog: vdc.u32 = vdc.rand()

    @vdc.constraint
    def override_cons(self):
        self.cfg.enabled == 1              # hard; overrides sub_cfg's soft==0

    @vdc.constraint
    def watchdog_range(self):
        self.watchdog in vdc.rangelist((50, 200))


@vdc.dataclass
class derived_c(base_c):                   # empty: inherits everything
    pass


@vdc.dataclass
class grandchild_c(derived_c):             # empty: 2 levels of inheritance
    pass


class TestDerivedThis(DcTestCase):

    def _check(self, obj):
        seen = set()
        for _ in range(20):
            obj.randomize()
            self.assertEqual(int(obj.cfg.enabled), 1)     # hard overrides soft
            self.assertTrue(50 <= int(obj.watchdog) <= 200)
            seen.add(int(obj.watchdog))
        self.assertGreater(len(seen), 1)

    def test_empty_derived_inherits_all(self):
        self._check(derived_c())

    def test_empty_grandchild_inherits_all(self):
        self._check(grandchild_c())


# --- same-named constraint override -----------------------------------------
@vdc.dataclass
class P(vdc.RandClass):
    v: vdc.u8 = vdc.rand()

    @vdc.constraint
    def r(self):
        self.v < 10


@vdc.dataclass
class Q(P):
    @vdc.constraint
    def r(self):                          # REPLACES P.r (not AND)
        self.v > 200


class TestConstraintOverride(DcTestCase):

    def test_same_name_replaces(self):
        q = Q()
        for _ in range(20):
            q.randomize()
            self.assertGreater(q.v, 200)  # Q.r wins; P.r (v<10) is gone
        # Only one constraint named 'r' survives in the merged model.
        names = [c.name for c in q._get_type_model().constraints]
        self.assertEqual(names.count("r"), 1)


# --- t_randc_extends: an inherited randc field still cycles ------------------
@vdc.dataclass
class Seq(vdc.RandClass):
    select: vdc.u4 = vdc.randc()          # 16-value cyclic field


@vdc.dataclass
class Seq2(Seq):                          # empty subclass
    pass


class TestRandcExtends(DcTestCase):

    def test_inherited_randc_cycles(self):
        s = Seq2()
        vals = []
        for _ in range(16):
            s.randomize()
            vals.append(int(s.select))
        # A full cycle visits every value in 0..15 exactly once.
        self.assertEqual(sorted(vals), list(range(16)))


# --- forgot-@vdc.dataclass on a level that adds fields -----------------------
class TestUndecoratedLevel(DcTestCase):

    def test_undecorated_empty_subclass_ok(self):
        # An undecorated subclass that adds NOTHING still inherits and solves.
        class BareDerived(P):
            pass
        d = BareDerived()
        for _ in range(10):
            d.randomize()
            self.assertLess(d.v, 10)       # inherited P.r

    def test_undecorated_level_with_field_errors(self):
        # Adding a field on an undecorated level is an actionable error, not a
        # cryptic failure deep in constraint lowering.
        class BadDerived(P):
            w: vdc.u8 = vdc.rand()

            @vdc.constraint
            def w_c(self):
                self.w > 200

        with self.assertRaises(TypeError) as cm:
            BadDerived().randomize()
        self.assertIn("@vdc.dataclass", str(cm.exception))
