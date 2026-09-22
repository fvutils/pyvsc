"""Symbolic rangelist bounds and plan-cache freshness (Stage 1 / S1.7b).

`_snapshot_rangelist` evaluates each `inside` range bound and puts the value in
the plan's freshness signature. For a **symbolic** bound — `rng(self.c, self.d)`
where `c`/`d` are rand — that value is the *previous solve's answer*, not a user
input, so the signature never matched and the plan was rebuilt on every call.

The fix records a placeholder for any bound that reads a used-rand field. What
must keep working is everything the snapshot was there for in the first place:

- a rangelist whose literals the user mutates (`rl.clear()` / `.extend(...)`)
  must still invalidate — covered by
  ``ve/unit/test_dvsolve_array_plan_cache.py::test_foreach_rangelist_mutation_invalidates``,
  which exercises the classic front-end (the dc constraint parser only accepts a
  literal ``rangelist(...)`` in the constraint body, so a mutable one cannot be
  expressed there);
- a bound that reads a **non-rand** field must still invalidate when that field
  changes;
- and the symbolic case must still produce correct stimulus, which is the part
  a stale plan would silently break.

See ``doc/notes/vdc_stage1_impl_plan.md`` §S1.7b.
"""
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.model import opt_flags
from vsc.model.randomizer import _PLAN_ATTR

from dc_test_case import DcTestCase


@vdc.dataclass
class SymRange(vdc.RandClass):
    """`b` inside a range whose endpoints are themselves rand."""
    b: vdc.u8 = vdc.rand()
    c: vdc.u8 = vdc.rand()
    d: vdc.u8 = vdc.rand()

    @vdc.constraint
    def k(self):
        self.c != 0
        self.d != 0
        self.c < self.d
        self.b.inside(vdc.rangelist(vdc.rng(self.c, self.d)))


@vdc.dataclass
class NonRandBound(vdc.RandClass):
    """`lo`/`hi` are NOT rand — a genuine user input the signature must track."""
    lo: vdc.u8 = vdc.field(default=10)
    hi: vdc.u8 = vdc.field(default=20)
    b: vdc.u8 = vdc.rand()

    @vdc.constraint
    def k(self):
        self.b.inside(vdc.rangelist(vdc.rng(self.lo, self.hi)))


class TestSymbolicRangelistPlan(DcTestCase):

    @staticmethod
    def _plan(cls):
        node = cls.__dict__.get(solve_view._SOLVE_MODEL_ATTR)
        return getattr(node.composite, _PLAN_ATTR, None) if node else None

    # ------------------------------------------------------------------ #
    # Correctness first — a stale plan here would be silent
    # ------------------------------------------------------------------ #

    def test_symbolic_range_is_respected(self):
        o = SymRange()
        for _ in range(60):
            o.randomize()
            self.assertNotEqual(0, o.c)
            self.assertNotEqual(0, o.d)
            self.assertLess(o.c, o.d)
            self.assertGreaterEqual(o.b, o.c)
            self.assertLessEqual(o.b, o.d)

    def test_symbolic_range_still_varies(self):
        """A plan that is reused must not pin the answer."""
        o = SymRange()
        seen = set()
        for _ in range(60):
            o.randomize()
            seen.add((o.b, o.c, o.d))
        self.assertGreater(len(seen), 5, "symbolic range collapsed to one answer")

    def test_non_rand_bounds_are_respected_as_they_change(self):
        o = NonRandBound()
        for lo, hi in ((10, 20), (200, 250), (0, 3), (100, 101)):
            o.lo, o.hi = lo, hi
            for _ in range(10):
                o.randomize()
                self.assertGreaterEqual(o.b, lo)
                self.assertLessEqual(o.b, hi)

    # ------------------------------------------------------------------ #
    # ...and the plan actually gets reused
    # ------------------------------------------------------------------ #

    def test_symbolic_range_keeps_its_plan(self):
        """The point of the fix. Without it the plan was rebuilt on every call
        (measured 29/29 rebuilds, 7.7x on create-many)."""
        if not opt_flags.NARROW_PLAN_SIG:
            self.skipTest("VSC_S1_NARROW_PLAN_SIG is off")
        o = SymRange()
        o.randomize()
        plan = self._plan(SymRange)
        if plan is None:
            self.skipTest("no Tier-A plan on this back-end (dv-solve only)")
        for _ in range(15):
            o.randomize()
            self.assertIs(plan, self._plan(SymRange), "plan was rebuilt")

    def test_switch_off_matches_switch_on(self):
        import random

        def run(narrow):
            saved = opt_flags.NARROW_PLAN_SIG
            opt_flags.NARROW_PLAN_SIG = narrow
            try:
                random.seed(9)
                o = SymRange()
                return [(o.randomize() or (o.b, o.c, o.d)) for _ in range(20)]
            finally:
                opt_flags.NARROW_PLAN_SIG = saved

        self.assertEqual(run(False), run(True))
