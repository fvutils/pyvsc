"""Fixed lookup-table index selection (`table[rand_idx] <cmp> const`).

When an array is **not randomized** — a fixed lookup table declared with
``vdc.field(...)`` — ``table[idx]`` is a pure *selector*, not a symbolic select:
the feasible index set is a compile-time constant. The dv-solve translator rewrites
``table[idx] <cmp> const`` into a membership constraint on the index
(``idx inside {i : table[i] <cmp> const}``), which is both far cheaper than an n-arm
select and strictly more solvable — the ITE encoding cannot reverse-propagate
``arm == K`` back to the index, so a plain ``table[idx] == K`` otherwise deferred.

Enablers landed with this feature:
  * ``vdc.field(size=N)`` / ``vdc.field(default_factory=lambda: [...])`` — non-rand
    fixed-size arrays (previously modelled as random-size and rejected);
  * ``RandInfoBuilder`` no longer pulls a non-rand table's elements into the randset
    (only the rand index is a solve var).

The rewrite is a dv-solve capability (boolector snapshots a symbolic index), so the
symbolic-index cases are dv-solve-gated; the fixed-table *declaration* itself works on
both backends and is checked with a constant index.
"""
import random

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.impl import ctor
import vsc.model.randomizer as rnd
from vsc.model.solve_failure import SolveFailure


class TestFixedTableSelect(DcTestCase):

    def _require_dvsolve(self):
        if ctor.get_solver_backend() != "dv-solve":
            self.skipTest("symbolic-index table select is a dv-solve capability "
                          "(boolector snapshots the index)")

    # ---- frontend: non-rand fixed-size tables (both backends) ------------- #
    def test_fixed_table_declaration_const_index(self):
        # A non-rand fixed table + a constant index resolves the element on both
        # backends, and the table is never assigned by the solver.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40])
            pick: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.tbl[2] == self.pick     # constant index -> element 30

        c = my_c()
        for i in range(10):
            random.seed(i)
            c.randomize()
            self.assertEqual([int(x) for x in c.tbl], [10, 20, 30, 40])
            self.assertEqual(int(c.pick), 30)

    def test_field_size_zero_filled(self):
        # `vdc.field(size=N)` with no values defaults to a zero-filled fixed table.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(size=4)
            pick: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.tbl[1] == self.pick

        c = my_c()
        c.randomize()
        self.assertEqual([int(x) for x in c.tbl], [0, 0, 0, 0])
        self.assertEqual(int(c.pick), 0)

    # ---- the selector rewrite (dv-solve) ---------------------------------- #
    def test_table_select_eq(self):
        # table[idx] == K : the case the ITE encoding could not reverse-solve.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] == 30

        c = my_c()
        for i in range(20):
            random.seed(i)
            c.randomize()
            self.assertEqual(int(c.idx), 2)   # only tbl[2] == 30

    def test_table_select_bound_spreads(self):
        # table[idx] < K selects the whole feasible index set, and idx spreads.
        self._require_dvsolve()

        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        self.addCleanup(rnd.restore_fallback_tally, snap)

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] < 35

        c = my_c()
        seen = set()
        for i in range(60):
            random.seed(i)
            c.randomize()
            self.assertLess(int(c.tbl[int(c.idx)]), 35)
            seen.add(int(c.idx))
        self.assertEqual(seen, {0, 1, 2}, "index set wrong/under-covered: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "selector rewrite deferred instead of serving natively")

    def test_table_select_duplicate_values(self):
        # A value that appears at multiple indices -> membership over all of them.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 20, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] == 20

        c = my_c()
        seen = set()
        for i in range(40):
            random.seed(i)
            c.randomize()
            self.assertEqual(int(c.tbl[int(c.idx)]), 20)
            seen.add(int(c.idx))
        self.assertEqual(seen, {1, 3})

    def test_table_select_flipped_operand(self):
        # const on the left: `K == table[idx]` rewrites the same way.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                40 == self.tbl[self.idx]

        c = my_c()
        for i in range(15):
            random.seed(i)
            c.randomize()
            self.assertEqual(int(c.idx), 3)

    def test_table_select_unsat(self):
        # No index matches -> the rewrite yields an empty membership -> UNSAT.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] == 99      # no such value

        c = my_c()
        with self.assertRaises(SolveFailure):
            c.randomize()

    def test_table_stays_fixed_and_lookup_val(self):
        # table[idx] == val (val rand): a functional lookup — val follows idx, the
        # table never changes, and idx covers its domain.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] == self.val

        c = my_c()
        seen = set()
        for i in range(60):
            random.seed(i)
            c.randomize()
            self.assertEqual([int(x) for x in c.tbl], [10, 20, 30, 40, 50])
            self.assertEqual(int(c.tbl[int(c.idx)]), int(c.val))
            seen.add(int(c.idx))
        self.assertEqual(seen, {0, 1, 2, 3, 4}, "idx did not spread: %s" % seen)

    def test_selector_rewrite_is_taken(self):
        # Lock that `table[idx] <cmp> const` actually takes the selector rewrite
        # (index membership), not the general ITE/select path.
        self._require_dvsolve()
        from vsc.model.solver import dvsolve_translator as _dt

        orig = _dt.DvSolveExprTranslator.try_const_table_select
        fired = {"n": 0}

        def _counting(self, e):
            r = orig(self, e)
            if r is not None:
                fired["n"] += 1
            return r

        _dt.DvSolveExprTranslator.try_const_table_select = _counting
        self.addCleanup(setattr, _dt.DvSolveExprTranslator,
                        "try_const_table_select", orig)

        @vdc.dataclass
        class my_c(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40, 50])
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.tbl[self.idx] >= 30

        c = my_c()
        for i in range(10):
            random.seed(i)
            c.randomize()
            self.assertGreaterEqual(int(c.tbl[int(c.idx)]), 30)
        self.assertGreater(fired["n"], 0,
                           "const-table selector rewrite was never taken")
