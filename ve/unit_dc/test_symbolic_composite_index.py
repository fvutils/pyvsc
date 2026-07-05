"""Symbolic (rand) index into an *object* array — Workstream C.

``arr[idx].field`` where ``arr`` is a ``list[<dataclass>]`` and ``idx`` is rand is
the composite-array counterpart of the scalar symbolic select (Workstream A/B). The
DC lowerer (``ir_lower._try_symbolic_composite_select``) rewrites it into a select
over the homogeneous scalar sub-field *column* ``[arr[0].field, arr[1].field, …]`` —
a synthetic scalar ``FieldArrayModel`` view whose elements are the real element
sub-field models. From there the existing scalar machinery takes over unchanged:
``RandInfoBuilder`` unifies the column + the index into one randset, and the dv-solve
translator emits the ITE / native select. So every scalar-select shape (equality,
bare bound, relational, functional lookup) now works one level up over object arrays.

Before this, ``arr[idx].field`` with a non-constant index died in DC lowering with
``NotImplementedError: composite-array subscripts must be constant``.

These are **dv-solve** capabilities: boolector snapshots the index at build time and
cannot co-solve a symbolic index (it produces a stale-snapshot, self-inconsistent
model), so the correctness tests skip on boolector — its role is the XCHECK oracle,
validating the finished dv-solve model when the index is concrete. The fixed
*declaration* + constant-index element access works on both backends. See
``doc/notes/dv_solve_symbolic_array_index_plan.md`` (Workstream C).
"""
import random

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.impl import ctor
import vsc.model.randomizer as rnd
from vsc.model.solve_failure import SolveFailure


@vdc.dataclass
class Item(vdc.RandClass):
    a: vdc.u8 = vdc.rand()


class TestSymbolicCompositeIndex(DcTestCase):

    # ---- helpers --------------------------------------------------------- #
    def _require_dvsolve(self):
        if ctor.get_solver_backend() != "dv-solve":
            self.skipTest("symbolic object-array select is a dv-solve capability "
                          "(boolector is the XCHECK oracle only)")

    def _no_fallback(self):
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        self.addCleanup(rnd.restore_fallback_tally, snap)

    # ---- declaration / constant index (both backends) -------------------- #
    def test_object_const_index(self):
        # A constant index into an object array resolves the element member on
        # both backends (the pre-existing concrete path, unchanged by WS-C).
        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)
            pick: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.items[2].a == self.pick
                self.pick == 9

        t = Top()
        for i in range(10):
            random.seed(i)
            t.randomize()
            self.assertEqual(int(t.items[2].a), 9)
            self.assertEqual(int(t.pick), 9)

    # ---- symbolic select over the sub-field column (dv-solve) ------------ #
    def test_object_select_eq(self):
        # arr[idx].a == K : idx spreads its domain, correctness every draw, native.
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.items[self.idx].a == 30

        t = Top()
        seen = set()
        for i in range(60):
            random.seed(i)
            t.randomize()
            idx = int(t.idx)
            seen.add(idx)
            self.assertTrue(0 <= idx < 5)
            self.assertEqual(int(t.items[idx].a), 30,
                             (idx, [int(e.a) for e in t.items]))
        self.assertEqual(seen, {0, 1, 2, 3, 4}, "idx did not spread: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "object select deferred instead of serving natively")

    def test_object_select_bare_bound(self):
        # arr[idx].a < K : the headline reach — was NotImplementedError in lowering.
        # A bare bound on the selected member forces every column element live.
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.items[self.idx].a < 10

        t = Top()
        seen = set()
        for i in range(60):
            random.seed(i)
            t.randomize()
            idx = int(t.idx)
            seen.add(idx)
            self.assertLess(int(t.items[idx].a), 10,
                            (idx, [int(e.a) for e in t.items]))
        self.assertEqual(seen, {0, 1, 2, 3, 4}, "idx did not spread: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "object bound-select deferred instead of serving natively")

    def test_object_select_relational_two_indices(self):
        # arr[i].a > arr[j].a with two independent rand indices.
        self._require_dvsolve()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 4
                self.j < 4
                self.i != self.j
                self.items[self.i].a > self.items[self.j].a

        t = Top()
        for k in range(40):
            random.seed(k)
            t.randomize()
            i, j = int(t.i), int(t.j)
            self.assertNotEqual(i, j)
            self.assertGreater(int(t.items[i].a), int(t.items[j].a), (i, j))

    def test_object_select_functional_lookup(self):
        # arr[idx].a == val (val rand): a functional lookup — val follows the
        # selected element, and idx covers its whole domain.
        self._require_dvsolve()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.items[self.idx].a == self.val

        t = Top()
        seen = set()
        for i in range(60):
            random.seed(i)
            t.randomize()
            idx = int(t.idx)
            seen.add(idx)
            self.assertEqual(int(t.items[idx].a), int(t.val))
        self.assertEqual(seen, {0, 1, 2, 3, 4}, "idx did not spread: %s" % seen)

    def test_object_select_picks_named_column(self):
        # An element with two members — the select must resolve the *named* column
        # (b), leaving a free, and correctly report the selected element.
        self._require_dvsolve()

        @vdc.dataclass
        class Two(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Two] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.items[self.idx].b == 7

        t = Top()
        for i in range(30):
            random.seed(i)
            t.randomize()
            idx = int(t.idx)
            self.assertEqual(int(t.items[idx].b), 7,
                             (idx, [(int(e.a), int(e.b)) for e in t.items]))

    def test_object_select_unsat(self):
        # arr[idx].a == 30 but every element pinned to 0 -> UNSAT.
        self._require_dvsolve()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.items[self.idx].a == 30
                with vdc.foreach(self.items) as it:
                    it.a == 0

        t = Top()
        with self.assertRaises(SolveFailure):
            t.randomize()

    # ---- scoping: multi-level access defers cleanly ---------------------- #
    def test_object_select_multilevel_defers(self):
        # arr[idx].sub.field — more than one symbolic level — must raise a clean,
        # documented error, never a silent mis-lower.
        self._require_dvsolve()

        @vdc.dataclass
        class Leaf(vdc.RandClass):
            c: vdc.u8 = vdc.rand()

        @vdc.dataclass
        class Mid(vdc.RandClass):
            b: Leaf = vdc.rand()

        @vdc.dataclass
        class Top(vdc.RandClass):
            a: list[Mid] = vdc.rand(size=3)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 3
                self.a[self.idx].b.c == 5

        t = Top()
        with self.assertRaises(NotImplementedError):
            t.randomize()

    # ---- lock the rewrite is actually taken ------------------------------ #
    def test_object_select_path_is_taken(self):
        self._require_dvsolve()
        from vsc.dc import ir_lower as _il

        orig = _il._try_symbolic_composite_select
        fired = {"n": 0}

        def _counting(idx_node, field_name, ctx):
            r = orig(idx_node, field_name, ctx)
            if r is not None:
                fired["n"] += 1
            return r

        _il._try_symbolic_composite_select = _counting
        self.addCleanup(setattr, _il, "_try_symbolic_composite_select", orig)

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 5
                self.items[self.idx].a >= 30

        t = Top()
        for i in range(10):
            random.seed(i)
            t.randomize()
            self.assertGreaterEqual(int(t.items[int(t.idx)].a), 30)
        self.assertGreater(fired["n"], 0,
                           "symbolic composite-select path was never taken")
