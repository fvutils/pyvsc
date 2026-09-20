"""Copy-in skipping (Stage 1 / S1.3): ``_apply_node`` no longer writes an
enabled rand field's stale instance value into the model before a solve that is
about to overwrite it.

Every test here is a *correctness condition* the skip depends on, written so it
fails loudly if the skip set ever widens past what is provable. The failure mode
this step can produce is silent — a solve that succeeds on stale inputs — so the
conditions are tested directly rather than inferred from the suite passing.

See ``doc/notes/vdc_stage1_impl_plan.md`` §S1.3.
"""
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.model import opt_flags
from vsc.model.solve_failure import SolveFailure

from dc_test_case import DcTestCase


# --------------------------------------------------------------------------
# Model classes (must live at module scope: dc constraints compile from source)
# --------------------------------------------------------------------------

@vdc.dataclass
class Plain(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b


@vdc.dataclass
class WithInput(vdc.RandClass):
    """A non-rand field read by a constraint — must always be copied in."""
    lo: vdc.u8 = vdc.field(default=0)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > self.lo
        self.a < 200


@vdc.dataclass
class Cyclic(vdc.RandClass):
    k: vdc.u4 = vdc.randc()

    @vdc.constraint
    def c(self):
        self.k < 10


@vdc.dataclass
class CoupledCyclic(vdc.RandClass):
    """A randc coupled to another rand field is NOT separable, so cyclic.py
    takes its exclusion fallback rather than the fast path. That fallback is
    where a stranded ``rand_mode=False`` turns into a pinned field."""
    k: vdc.u4 = vdc.randc()
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a == self.k * 2
        self.k < 10


@vdc.dataclass
class Arr(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=8)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


@vdc.dataclass
class RandSzArr(vdc.RandClass):
    sz: vdc.u8 = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(max_size=8)

    @vdc.constraint
    def c(self):
        self.arr.size == self.sz
        self.sz > 2
        self.sz <= 8
        with vdc.foreach(self.arr) as it:
            it < 100


@vdc.dataclass
class Leaf(vdc.RandClass):
    x: vdc.u8 = vdc.rand()


@vdc.dataclass
class NonRandParent(vdc.RandClass):
    """`sub` is NOT declared rand, so `sub.x` is never used-rand and must be
    copied in even though it is declared rand at its own level."""
    sub: Leaf = vdc.field(default_factory=Leaf)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > self.sub.x
        self.a < 250


@vdc.dataclass
class RandParent(vdc.RandClass):
    sub: Leaf = vdc.rand()
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a == self.sub.x


@vdc.dataclass
class Unsat(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > 10
        self.a < 5


@vdc.dataclass
class PreHook(vdc.RandClass):
    lo: vdc.u8 = vdc.field(default=0)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > self.lo
        self.a < 200

    def pre_randomize(self):
        self.lo = 150


class TestSkipCopyin(DcTestCase):

    # ------------------------------------------------------------------ #
    # What is in the skip set, and what deliberately is not
    # ------------------------------------------------------------------ #

    def _skip_of(self, cls):
        o = cls()
        o.randomize()
        return cls.__dict__[solve_view._SOLVE_MODEL_ATTR].skip_copyin

    def test_enabled_rand_scalars_are_skipped(self):
        self.assertEqual({"a", "b"}, set(self._skip_of(Plain)))

    def test_non_rand_input_is_not_skipped(self):
        skip = self._skip_of(WithInput)
        self.assertNotIn("lo", skip)
        self.assertIn("a", skip)

    def test_randc_is_not_skipped(self):
        """cyclic.py leaves rand_mode=False after its fast path; the next
        _apply_node is what restores it. Skipping would strand the field at
        rand_mode=False, and the exclusion fallback would then treat it as a
        constant at its stale value.

        This is a *structural* assertion on purpose. Widening the skip set to
        include randc does not break the common fast path (cyclic re-sets
        rand_mode=False before each solve anyway), so a behavioural test alone
        would not catch the regression -- only the bail-to-exclusion path
        would, and only sometimes. See test_coupled_randc_cycles."""
        self.assertNotIn("k", self._skip_of(Cyclic))
        self.assertNotIn("k", self._skip_of(CoupledCyclic))

    def test_coupled_randc_cycles(self):
        """The non-separable randc path (cyclic's exclusion fallback)."""
        o = CoupledCyclic()
        seen = []
        for _ in range(10):
            o.randomize()
            self.assertEqual(o.a, o.k * 2)
            seen.append(o.k)
        self.assertEqual(10, len(set(seen)), "randc repeated within a cycle")

    def test_fixed_size_rand_array_is_skipped(self):
        self.assertIn("arr", self._skip_of(Arr))

    def test_rand_size_array_is_not_skipped(self):
        skip = self._skip_of(RandSzArr)
        self.assertNotIn("arr", skip)

    def test_rand_field_under_non_rand_composite_is_not_skipped(self):
        o = NonRandParent()
        o.randomize()
        root = NonRandParent.__dict__[solve_view._SOLVE_MODEL_ATTR]
        self.assertIn("a", root.skip_copyin)
        self.assertEqual(frozenset(), root.children["sub"].skip_copyin)

    def test_rand_field_under_rand_composite_is_skipped(self):
        o = RandParent()
        o.randomize()
        root = RandParent.__dict__[solve_view._SOLVE_MODEL_ATTR]
        self.assertIn("x", root.children["sub"].skip_copyin)

    # ------------------------------------------------------------------ #
    # The five correctness conditions
    # ------------------------------------------------------------------ #

    def test_c1_rand_mode_disabled_field_is_a_constant(self):
        """A rand_mode(False) field becomes a constant at its *current* value,
        so it must reach the model. Exercised across repeated randomizes."""
        o = Plain()
        o.a = 7
        o.set_rand_mode("a", False)
        for _ in range(8):
            o.randomize()
            self.assertEqual(7, o.a)
            self.assertGreater(o.b, 7)

    def test_c1b_rand_mode_restored_after_reenable(self):
        """Re-enabling must actually re-enable. The model's rand_mode was set
        to False by a previous apply; the node's rm_dirty flag forces one full
        apply so it gets restored."""
        o = Plain()
        o.a = 7
        o.set_rand_mode("a", False)
        o.randomize()
        self.assertEqual(7, o.a)

        o.set_rand_mode("a", True)
        seen = set()
        for _ in range(40):
            o.randomize()
            seen.add(o.a)
        self.assertGreater(len(seen), 1, "field stayed pinned after re-enable")

    def test_c1c_rand_mode_disabled_on_a_second_instance(self):
        """The solve model is shared per type, so a rand_mode override applied
        to one instance must not leak into another."""
        a = Plain()
        a.a = 9
        a.set_rand_mode("a", False)
        a.randomize()
        self.assertEqual(9, a.a)

        b = Plain()
        seen = set()
        for _ in range(40):
            b.randomize()
            seen.add(b.a)
        self.assertGreater(len(seen), 1, "override leaked to another instance")

    def test_c2_non_rand_input_reaches_the_solver(self):
        o = WithInput()
        for lo in (10, 50, 150, 190):
            o.lo = lo
            for _ in range(5):
                o.randomize()
                self.assertGreater(o.a, lo)
                self.assertLess(o.a, 200)

    def test_c3_solve_failure_writes_nothing_back(self):
        o = Unsat()
        o.a = 3
        with self.assertRaises(SolveFailure):
            o.randomize()
        self.assertEqual(3, o.a)

    def test_c4_pre_randomize_mutation_is_invisible_to_the_solver(self):
        """DOCUMENTS CURRENT BEHAVIOUR, pre-dating S1.3.

        vdc calls get_solve_model() (hence _apply_node) before do_randomize runs
        pre_randomize, so a hook that mutates a field is not seen by this
        solve -- it takes effect on the *next* one. This test exists so the wart
        cannot be blamed on, or silently changed by, the copy-in skip. If it
        ever starts failing because the ordering was fixed, that is a
        deliberate improvement: update this test with the fix.
        """
        o = PreHook()
        o.lo = 0
        o.randomize()
        self.assertEqual(150, o.lo)          # the hook did run...
        # ...but this solve used lo=0, so a value <= 150 is reachable.
        low_seen = o.a <= 150
        for _ in range(40):
            o.lo = 0
            o.randomize()
            low_seen = low_seen or o.a <= 150
        self.assertTrue(low_seen,
                        "pre_randomize mutation unexpectedly reached the solver")

    def test_c5_plan_cache_does_not_depend_on_stale_rand_values(self):
        """A rand field's model value must not participate in plan freshness --
        if it did, skipping the copy-in would change cache behaviour."""
        o = Plain()
        o.randomize()
        o.a = 200          # a stale rand value nothing should notice
        o.b = 201
        for _ in range(10):
            o.randomize()
            self.assertLess(o.a, o.b)

    # ------------------------------------------------------------------ #
    # The switch is a performance switch, not a behavioural one
    # ------------------------------------------------------------------ #

    def _stimulus(self, cls, extract, n=20, skip=True):
        import random
        saved = opt_flags.SKIP_COPYIN
        opt_flags.SKIP_COPYIN = skip
        try:
            random.seed(11)
            o = cls()
            return [extract(o) for _ in range(n) if o.randomize() is None]
        finally:
            opt_flags.SKIP_COPYIN = saved

    def test_switch_off_matches_switch_on(self):
        cases = [
            (Plain, lambda o: (o.a, o.b)),
            (Arr, lambda o: list(o.arr)),
            (WithInput, lambda o: o.a),
            (RandParent, lambda o: (o.a, o.sub.x)),
            (NonRandParent, lambda o: (o.a, o.sub.x)),
            (Cyclic, lambda o: o.k),
            (CoupledCyclic, lambda o: (o.k, o.a)),
            (RandSzArr, lambda o: (o.sz, list(o.arr))),
        ]
        for cls, extract in cases:
            with self.subTest(cls=cls.__name__):
                self.assertEqual(self._stimulus(cls, extract, skip=False),
                                 self._stimulus(cls, extract, skip=True))

    def test_randc_still_cycles(self):
        o = Cyclic()
        seen = [((o.randomize() or o.k)) for _ in range(10)]
        self.assertEqual(10, len(set(seen)), "randc repeated within a cycle")

    def test_rand_size_array_stays_consistent(self):
        o = RandSzArr()
        for _ in range(20):
            o.randomize()
            self.assertEqual(o.sz, len(o.arr))
            self.assertTrue(all(v < 100 for v in o.arr), o.arr)
