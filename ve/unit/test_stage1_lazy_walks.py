"""Pay-per-use housekeeping walks (Stage 1 / S1.4).

Two of the unconditional O(n) model walks `do_randomize` used to run on every
randomize() are now conditional:

- **C1** the soft-priority clear runs on the plan-cache *cold* path only. On a
  Tier-A hit the clear was immediately undone by `plan.restore_soft_priorities`,
  so it was a round trip to the same state.
- **C2** the constraint-override rollback runs only when something actually
  installed an override, tracked by a counter the *installer* maintains rather
  than inferred from the model's shape.

Both are only safe if their skip conditions hold exactly, and both fail
*silently* if they don't — a wrong soft-relaxation order or a stale overridden
constraint still produces a legal-looking solution. So the invariants are
asserted directly, and every case is also checked for stimulus identity against
the same run with `VSC_S1_LAZY_WALKS` off.

See ``doc/notes/vdc_stage1_impl_plan.md`` §S1.4.
"""
import random
import unittest

import vsc
from vsc.model import opt_flags
from vsc.visitors import constraint_override_visitor as override

from vsc_test_case import VscTestCase


@vsc.randobj
class Soft(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(16)
        self.b = vsc.rand_bit_t(16)

    @vsc.constraint
    def c(self):
        vsc.soft(self.a == 100)
        vsc.soft(self.b == 200)
        self.b > self.a


@vsc.randobj
class SoftUnsat(object):
    """The soft that must lose: relaxation order is what this tests."""
    def __init__(self):
        self.a = vsc.rand_bit_t(16)

    @vsc.constraint
    def c(self):
        vsc.soft(self.a == 100)
        self.a > 500


@vsc.randobj
class Arr(object):
    def __init__(self):
        self.arr = vsc.rand_list_t(vsc.uint8_t(), 16)

    @vsc.constraint
    def c(self):
        with vsc.foreach(self.arr) as it:
            it > 2
            it < 250


@vsc.randobj
class Dist(object):
    def __init__(self):
        self.k = vsc.rand_bit_t(8)

    @vsc.constraint
    def c(self):
        vsc.dist(self.k, [vsc.weight(0, 10),
                          vsc.weight((1, 3), 80),
                          vsc.weight(4, 10)])


class TestLazyWalks(VscTestCase):

    def _run(self, cls, extract, n=15, lazy=True):
        saved = opt_flags.LAZY_WALKS
        opt_flags.LAZY_WALKS = lazy
        try:
            random.seed(3)
            vsc.random.seed(3)
            o = cls()
            out = []
            for _ in range(n):
                o.randomize()
                out.append(extract(o))
            return out
        finally:
            opt_flags.LAZY_WALKS = saved

    # ------------------------------------------------------------------ #
    # C2 — the override counter is the whole safety argument
    # ------------------------------------------------------------------ #

    @staticmethod
    def _overrides_in_tree(o):
        """ConstraintOverrideModels still reachable from the field-model tree.

        This, not a global counter, is the invariant C2 has to preserve: after
        randomize() returns, the model must be back to its original
        constraints. (A counter of outstanding installs cannot be used — the
        builders also override constraints inside *inline* constraint objects,
        which the rollback walk never traverses, so such a counter drifts up
        without bound. That is what the per-call delta in
        ``constraint_override_visitor`` exists to avoid.)"""
        from vsc.model.constraint_override_model import ConstraintOverrideModel
        from vsc.model.model_visitor import ModelVisitor

        class _Collect(ModelVisitor):
            def __init__(self):
                super().__init__()
                self.found = []
                self._seen = set()

            def visit_constraint_override(self, c):
                self.found.append(c)

            def visit_composite_field(self, f):
                if f not in self._seen:
                    self._seen.add(f)
                    super().visit_composite_field(f)

        v = _Collect()
        o.get_model().accept(v)
        return v.found

    def test_foreach_overrides_are_rolled_back(self):
        """`foreach` expansion installs overrides on the cold path. Every one
        must be rolled back, or a later solve sees an expansion built for a
        stale array."""
        o = Arr()
        for _ in range(6):
            o.randomize()
            self.assertEqual([], self._overrides_in_tree(o))

    def test_dist_overrides_are_rolled_back(self):
        o = Dist()
        for _ in range(6):
            o.randomize()
            self.assertEqual([], self._overrides_in_tree(o))

    def test_inline_constraints_still_roll_back(self):
        """Inline constraints force the cold path on every call, so overrides
        are installed *and* must be rolled back every solve."""
        o = Arr()
        for i in range(6):
            with o.randomize_with() as it:
                it.arr[0] == 10 + i
            self.assertEqual(10 + i, o.arr[0])
            self.assertEqual([], self._overrides_in_tree(o))

    def test_install_during_a_call_forces_the_walk(self):
        """Direct check of the gate: a call that installs must run the walk.
        `randomize_with` on an array installs (inline + foreach expansion), so
        the install counter must advance across it."""
        o = Arr()
        o.randomize()                       # warm the plan cache
        before = override.installs
        with o.randomize_with() as it:
            it.arr[1] == 7
        self.assertGreater(override.installs, before)
        self.assertEqual([], self._overrides_in_tree(o))

    def test_foreach_constraints_still_hold_across_many_solves(self):
        o = Arr()
        for _ in range(20):
            o.randomize()
            self.assertTrue(all(2 < v < 250 for v in o.arr), list(o.arr))

    # ------------------------------------------------------------------ #
    # C1 — soft relaxation must survive the clear moving to the cold path
    # ------------------------------------------------------------------ #

    def test_soft_is_honoured_when_satisfiable(self):
        o = Soft()
        for _ in range(20):
            o.randomize()
            self.assertEqual(100, o.a)
            self.assertEqual(200, o.b)

    def test_soft_is_dropped_when_unsatisfiable(self):
        """Repeatedly, so the *cached-plan* path is exercised, not just the
        first cold build — that is where a zeroed priority would show up."""
        o = SoftUnsat()
        for _ in range(20):
            o.randomize()
            self.assertGreater(o.a, 500)

    def test_soft_priorities_do_not_accumulate_across_cold_builds(self):
        """The invariant C1 actually rests on.

        `RandInfoBuilder.visit_constraint_soft` does ``c.priority +=
        self._soft_priority`` — it *accumulates*. The clear exists to zero that
        before each rebuild, so C1 is correct precisely because the clear now
        runs on the same path as the rebuild. Inline constraints force a cold
        build every call, so priorities would grow without bound if the clear
        were dropped or mis-placed.
        """
        o = Soft()
        seen = []
        for i in range(6):
            with o.randomize_with() as it:
                it.a != 0
            seen.append([c.priority for c in self._soft_models(o)])
        self.assertTrue(all(p == seen[0] for p in seen),
                        "soft priorities drifted across cold builds: %r" % seen)

    @staticmethod
    def _soft_models(o):
        from vsc.model.constraint_soft_model import ConstraintSoftModel
        from vsc.model.model_visitor import ModelVisitor

        class _Collect(ModelVisitor):
            def __init__(self):
                super().__init__()
                self.found = []
                self._seen = set()

            def visit_constraint_soft(self, c):
                self.found.append(c)

            def visit_composite_field(self, f):
                if f not in self._seen:
                    self._seen.add(f)
                    super().visit_composite_field(f)

        v = _Collect()
        o.get_model().accept(v)
        return v.found

    def test_soft_priorities_are_not_left_stale_across_types(self):
        a, b = Soft(), SoftUnsat()
        for _ in range(10):
            a.randomize()
            b.randomize()
            self.assertEqual(100, a.a)
            self.assertGreater(b.a, 500)

    # ------------------------------------------------------------------ #
    # The switch is a performance switch, not a behavioural one
    # ------------------------------------------------------------------ #

    def test_switch_off_matches_switch_on(self):
        cases = [
            (Soft, lambda o: (o.a, o.b)),
            (SoftUnsat, lambda o: o.a),
            (Arr, lambda o: list(o.arr)),
            (Dist, lambda o: o.k),
        ]
        for cls, extract in cases:
            with self.subTest(cls=cls.__name__):
                self.assertEqual(self._run(cls, extract, lazy=False),
                                 self._run(cls, extract, lazy=True))

    def test_dist_shape_unchanged(self):
        """A walk skip must not be able to buy speed with distribution."""
        counts = {}
        o = Dist()
        for _ in range(2000):
            o.randomize()
            counts[o.k] = counts.get(o.k, 0) + 1
        mid = sum(counts.get(v, 0) for v in (1, 2, 3))
        self.assertGreater(mid, 1200, counts)      # ~80% of 2000
        self.assertLess(mid, 1900, counts)


if __name__ == "__main__":
    unittest.main()
