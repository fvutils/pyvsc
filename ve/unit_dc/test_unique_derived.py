"""``unique`` over a whole array, over a derived class, and over *symbolically
selected* elements — dc adaptation of ``t_constraint_unq_arr_derived`` plus the
new symbolic-select unique shapes.

The Verilator source declares an enum array in a base class and a derived class,
each with ``unique {pmp_reg}`` over the *whole* array plus per-element bounds
(``pmp_reg[0] inside {1,2}``), then checks ``pmp_reg[0] != pmp_reg[1]`` over 100
draws. Despite the "derived array" name, it has **no symbolic index** — "derived"
is the *derived class*, and the bounds use constant subscripts. Whole-array
``unique`` (both back-ends expand the array operand into its elements) + class
inheritance already carry it, so that part runs on both back-ends.

The genuinely-new capability is ``unique`` over elements chosen by a *rand* index —
``unique {arr[i], arr[j]}`` and, over object arrays, ``unique {a[i].v, a[j].v}``.
Each operand is a symbolic select (Workstreams A/B for scalar arrays, C for the
object-array column), so the select's arms must be co-solved with the indices and
the distinctness — which only dv-solve does (boolector snapshots the index and
``SolveFailure``s). Those shapes are dv-solve-gated.
"""
import random
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.impl import ctor
import vsc.model.randomizer as rnd
from vsc.model.solve_failure import SolveFailure


class EnumType(IntEnum):
    ZERO = 0
    RA = 1
    SP = 2
    GP = 3
    TP = 4
    T0 = 5
    T1 = 6


@vdc.dataclass
class Base(vdc.RandClass):
    b_scratch_reg: EnumType = vdc.rand()
    b_pmp_reg: list[EnumType] = vdc.rand(size=2)
    b_sp: EnumType = vdc.rand()

    @vdc.constraint
    def b_example(self):
        vdc.unique(self.b_pmp_reg)
        self.b_pmp_reg[0] > 0
        self.b_pmp_reg[0] < 3
        self.b_pmp_reg[1] > 0
        self.b_pmp_reg[1] < 3


@vdc.dataclass
class Foo(Base):
    scratch_reg: EnumType = vdc.rand()
    pmp_reg: list[EnumType] = vdc.rand(size=2)
    sp: EnumType = vdc.rand()

    @vdc.constraint
    def example(self):
        vdc.unique(self.pmp_reg)
        self.pmp_reg[0] > 0
        self.pmp_reg[0] < 3
        self.pmp_reg[1] > 0
        self.pmp_reg[1] < 3


@vdc.dataclass
class Item(vdc.RandClass):
    v: vdc.u8 = vdc.rand()


class TestUniqueDerived(DcTestCase):

    def _require_dvsolve(self):
        if ctor.get_solver_backend() != "dv-solve":
            self.skipTest("symbolic-index unique is a dv-solve capability "
                          "(boolector snapshots the index)")

    def _no_fallback(self):
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        self.addCleanup(rnd.restore_fallback_tally, snap)

    # ---- literal adaptation: whole-array unique + derived (both backends) - #
    def test_whole_array_unique_derived(self):
        # The .v check: over 100 draws pmp_reg[0] != pmp_reg[1], and each element
        # inside {1,2}. The inherited base constraint holds identically on
        # b_pmp_reg. With bounds {1,2} and two distinct elements, each array is a
        # permutation of (RA, SP).
        foo = Foo()
        for i in range(100):
            random.seed(i)
            foo.randomize()
            p = [int(x) for x in foo.pmp_reg]
            b = [int(x) for x in foo.b_pmp_reg]
            self.assertNotEqual(p[0], p[1], "pmp_reg not unique: %s" % p)
            self.assertTrue(all(0 < x < 3 for x in p), p)
            self.assertEqual(set(p), {EnumType.RA, EnumType.SP})
            self.assertNotEqual(b[0], b[1], "b_pmp_reg not unique: %s" % b)
            self.assertTrue(all(0 < x < 3 for x in b), b)

    def test_whole_array_unique_varies(self):
        # Uniqueness is enforced without freezing the ordering — both permutations
        # of (RA, SP) should appear across the corpus.
        foo = Foo()
        seen = set()
        for i in range(60):
            random.seed(i)
            foo.randomize()
            seen.add(tuple(int(x) for x in foo.pmp_reg))
        self.assertEqual(seen, {(1, 2), (2, 1)}, "ordering never varied: %s" % seen)

    def test_whole_array_unique_wide(self):
        # A wider whole-array unique (u4, size 6) still holds and varies — the
        # array-operand expansion + pairwise-!= scales past the size-2 corpus case.
        @vdc.dataclass
        class Regs(vdc.RandClass):
            r: list[vdc.u4] = vdc.rand(size=6)

            @vdc.constraint
            def c(self):
                vdc.unique(self.r)

        regs = Regs()
        for i in range(20):
            random.seed(i)
            regs.randomize()
            vals = [int(x) for x in regs.r]
            self.assertEqual(len(set(vals)), 6, "not all distinct: %s" % vals)

    # ---- new: unique over symbolically-selected elements (dv-solve) ------ #
    def test_symbolic_unique_scalar(self):
        # unique {arr[i], arr[j]} with rand i != j: the two selected elements must
        # differ. Bounding both selections to a small window forces distinctness to
        # bite on the *selected* elements, not just trivially on the whole array.
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class Sel(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=6)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 6
                self.j < 6
                self.i != self.j
                vdc.unique(self.arr[self.i], self.arr[self.j])
                self.arr[self.i] < 4
                self.arr[self.j] < 4

        t = Sel()
        for s in range(50):
            random.seed(s)
            t.randomize()
            i, j = int(t.i), int(t.j)
            vi, vj = int(t.arr[i]), int(t.arr[j])
            self.assertNotEqual(i, j)
            self.assertNotEqual(vi, vj, (i, j, [int(x) for x in t.arr]))
            self.assertTrue(vi < 4 and vj < 4)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "symbolic scalar unique deferred instead of native")

    def test_symbolic_unique_object_column(self):
        # unique {a[i].v, a[j].v, a[k].v} over an OBJECT array via three rand
        # indices — the sub-field-column select (Workstream C) composed inside a
        # unique. Three distinct members drawn from a 3-value window {0,1,2}.
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()
            k: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 5
                self.j < 5
                self.k < 5
                self.i != self.j
                self.j != self.k
                self.i != self.k
                vdc.unique(self.items[self.i].v,
                           self.items[self.j].v,
                           self.items[self.k].v)
                self.items[self.i].v < 3
                self.items[self.j].v < 3
                self.items[self.k].v < 3

        t = Top()
        for s in range(50):
            random.seed(s)
            t.randomize()
            i, j, k = int(t.i), int(t.j), int(t.k)
            vs = [int(t.items[x].v) for x in (i, j, k)]
            self.assertEqual(len(set([i, j, k])), 3)
            self.assertEqual(len(set(vs)), 3, (i, j, k, vs))
            self.assertTrue(all(x < 3 for x in vs), vs)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "symbolic object-column unique deferred instead of native")

    def test_symbolic_unique_unsat(self):
        # Three selected elements must be distinct but are all bounded < 2 (only
        # values {0,1}) -> pigeonhole UNSAT.
        self._require_dvsolve()

        @vdc.dataclass
        class Top(vdc.RandClass):
            items: list[Item] = vdc.rand(size=5)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()
            k: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 5
                self.j < 5
                self.k < 5
                self.i != self.j
                self.j != self.k
                self.i != self.k
                vdc.unique(self.items[self.i].v,
                           self.items[self.j].v,
                           self.items[self.k].v)
                self.items[self.i].v < 2
                self.items[self.j].v < 2
                self.items[self.k].v < 2

        t = Top()
        with self.assertRaises(SolveFailure):
            t.randomize()
