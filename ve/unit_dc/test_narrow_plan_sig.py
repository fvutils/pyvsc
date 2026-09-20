"""Narrowed plan-cache freshness signature (Stage 1 / S1.7).

The Tier-A plan used to snapshot the value of *every* non-rand field in
``bound_m``, so writing any non-rand field between solves invalidated the plan
and forced a full rebuild — a measured 7.6x cliff on the config/knob pattern,
for a field no constraint mentions.

Only a non-rand field some constraint actually *reads* can change the solution,
and ``RandSet.add_field`` is called by ``RandInfoBuilder`` for exactly those, so
the union of ``all_fields()`` over the randsets is the right set.

The dangerous direction is the signature being **too narrow** — a stale plan
reused after an input changed produces a legal-looking but wrong solution, or
misses an UNSAT. Those are the cases tested first.

See ``doc/notes/vdc_stage1_impl_plan.md`` §S1.7.
"""
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.model import opt_flags
from vsc.model.randomizer import _PLAN_ATTR
from vsc.model.solve_failure import SolveFailure

from dc_test_case import DcTestCase

# The Tier-A plan cache is a dv-solve-only path (`plan_ok` requires it), so the
# structural assertions about the signature only mean anything there; they skip
# elsewhere (see _tracked). The behavioural tests run on both back-ends.


@vdc.dataclass
class ReadInput(vdc.RandClass):
    """`lo` is read by a constraint: it MUST stay in the signature."""
    lo: vdc.u8 = vdc.field(default=0)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > self.lo
        self.a < 200


@vdc.dataclass
class ConstOnly(vdc.RandClass):
    """A hard constraint over ONLY non-rand fields. If `lo` fell out of the
    signature, a plan built while it held would be reused after it stopped
    holding, and the UNSAT would be missed entirely."""
    lo: vdc.u8 = vdc.field(default=3)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.lo < 5
        self.a < 200


@vdc.dataclass
class Knob(vdc.RandClass):
    """`seen` is read by nothing — the field the narrowing is for."""
    seen: vdc.u8 = vdc.field(default=0)
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b

    def post_randomize(self):
        self.seen = self.a


@vdc.dataclass
class Both(vdc.RandClass):
    lo: vdc.u8 = vdc.field(default=0)
    seen: vdc.u8 = vdc.field(default=0)
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > self.lo
        self.a < 200


class TestNarrowPlanSig(DcTestCase):

    @staticmethod
    def _plan(cls):
        node = cls.__dict__[solve_view._SOLVE_MODEL_ATTR]
        return getattr(node.composite, _PLAN_ATTR, None)

    def _tracked(self, cls, narrowed=False):
        """Names of fields whose *value* the plan's signature tracks.

        ``narrowed=True`` marks an assertion about the *optimization* rather
        than about behaviour, so it skips with the switch off — the
        all-switches-off run has to stay green (plan §3.6)."""
        plan = self._plan(cls)
        if plan is None:
            self.skipTest("no Tier-A plan on this back-end (dv-solve only)")
        if narrowed and not opt_flags.NARROW_PLAN_SIG:
            self.skipTest("VSC_S1_NARROW_PLAN_SIG is off")
        return {f.name for f, _was_rand, val in plan.field_state if val is not None}

    # ------------------------------------------------------------------ #
    # Too narrow would be silent-wrong: these come first
    # ------------------------------------------------------------------ #

    def test_constraint_read_input_stays_tracked(self):
        o = ReadInput()
        o.randomize()
        self.assertIn("lo", self._tracked(ReadInput))

    def test_changing_a_read_input_is_honoured(self):
        o = ReadInput()
        for lo in (10, 50, 150, 190, 5):
            o.lo = lo
            for _ in range(5):
                o.randomize()
                self.assertGreater(o.a, lo)
                self.assertLess(o.a, 200)

    def test_const_only_constraint_input_stays_tracked(self):
        o = ConstOnly()
        o.randomize()
        self.assertIn("lo", self._tracked(ConstOnly))

    def test_const_only_constraint_still_detects_unsat(self):
        o = ConstOnly()
        o.randomize()                     # lo=3, satisfiable
        o.lo = 10                         # now violated
        with self.assertRaises(SolveFailure):
            o.randomize()

    def test_rand_mode_toggle_still_invalidates(self):
        """is_used_rand is tracked for every field regardless of the narrowing:
        a rand_mode toggle changes the partitioning, not just a value."""
        o = Both()
        o.lo = 10
        o.randomize()
        self.assertGreater(o.a, 10)

        o.a = 50                          # still satisfies a > lo
        o.set_rand_mode("a", False)
        o.randomize()
        self.assertEqual(50, o.a)         # pinned

        o.set_rand_mode("a", True)
        for _ in range(5):
            o.randomize()
            self.assertGreater(o.a, 10)

    # ------------------------------------------------------------------ #
    # ...and the narrowing actually happens
    # ------------------------------------------------------------------ #

    def test_unreferenced_non_rand_field_is_not_tracked(self):
        o = Knob()
        o.randomize()
        self.assertNotIn("seen", self._tracked(Knob, narrowed=True))

    def test_mixed_class_tracks_only_the_read_field(self):
        o = Both()
        o.randomize()
        self.assertEqual({"lo"}, self._tracked(Both, narrowed=True))

    def test_knob_pattern_keeps_the_plan(self):
        """The point of the whole step: a post_randomize hook writing an
        unreferenced non-rand field must not evict the plan every solve."""
        o = Knob()
        o.randomize()
        self._tracked(Knob, narrowed=True)   # skips when the switch is off
        plan = self._plan(Knob)
        for _ in range(10):
            o.randomize()
            self.assertIs(plan, self._plan(Knob), "plan was rebuilt")
            self.assertLess(o.a, o.b)
            self.assertEqual(o.seen, o.a)

    # ------------------------------------------------------------------ #
    # Switch identity
    # ------------------------------------------------------------------ #

    def test_switch_off_matches_switch_on(self):
        import random

        def run(narrow):
            saved = opt_flags.NARROW_PLAN_SIG
            opt_flags.NARROW_PLAN_SIG = narrow
            try:
                random.seed(5)
                o = Both()
                out = []
                for i in range(15):
                    o.lo = 10 * (i % 5)
                    o.randomize()
                    out.append((o.lo, o.a))
                return out
            finally:
                opt_flags.NARROW_PLAN_SIG = saved

        self.assertEqual(run(False), run(True))
