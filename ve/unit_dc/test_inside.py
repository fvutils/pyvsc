"""``inside`` membership — dc adaptation of ``t_inside`` / ``t_inside_unbounded`` /
``t_inside_unpacked``.

The Verilator sources are mostly *evaluation* tests (they check the boolean value of
``expr inside {...}``). Re-cast for a randomization library, each becomes a
**constraint** that forces membership, and the solved value is checked to lie in the
set (or, for a negative/empty set, the solve must fail). Covered:

  * value-set and enum membership (``num inside {ONE, THREE}``), ``inside`` + ``not_inside``;
  * multi-range unions ``{[1:2], [3:5]}`` and range-boundary inclusivity ``[0:4]``;
  * ``x inside {array}`` — the ``t_inside_unpacked`` shape, membership against a whole
    array's elements, for both a fixed lookup table and a rand array;
  * a reversed/empty range ``[5:3]`` matches nothing → UNSAT alone, and is a no-op when
    unioned with a valid range.

These are non-symbolic membership constraints, so every case runs on **both** back-ends.
Dropped per the Tier-3 caveats: ``==?``/``?`` wildcard bit-matching, ``x`` values, real
operands (no dc analog), and the unbounded ``$`` range endpoint (``t_inside_unbounded``);
a ``[$:100]`` bound is just ``[0:100]`` over an unsigned field's domain, already covered
by the explicit-range cases. Discrete-set membership is asserted by containment only
(not spread): dv-solve legally biases which set members it picks, mirroring the existing
``test_in`` posture.
"""
import random
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.model.solve_failure import SolveFailure


class Num(IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3


class TestInside(DcTestCase):

    # ---- enum membership (t_inside is_odd: number inside {ONE, THREE}) ---- #
    def test_enum_inside(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            n: Num = vdc.rand()

            @vdc.constraint
            def c(self):
                self.n.inside(vdc.rangelist(Num.ONE, Num.THREE))

        c = C()
        for i in range(30):
            random.seed(i)
            c.randomize()
            self.assertIn(int(c.n), (Num.ONE, Num.THREE))

    def test_enum_not_inside(self):
        # The complement: number NOT in {ONE, THREE} -> {ZERO, TWO}.
        @vdc.dataclass
        class C(vdc.RandClass):
            n: Num = vdc.rand()

            @vdc.constraint
            def c(self):
                self.n.not_inside(vdc.rangelist(Num.ONE, Num.THREE))

        c = C()
        for i in range(30):
            random.seed(i)
            c.randomize()
            self.assertIn(int(c.n), (Num.ZERO, Num.TWO))

    # ---- ranges: union + boundary inclusivity ---------------------------- #
    def test_multi_range_union(self):
        # a inside {[1:2], [3:5]} : the union {1,2,3,4,5}, and it spreads over all.
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a.inside(vdc.rangelist(vdc.rng(1, 2), vdc.rng(3, 5)))

        c = C()
        seen = set()
        for i in range(60):
            random.seed(i)
            c.randomize()
            self.assertIn(int(c.a), (1, 2, 3, 4, 5))
            seen.add(int(c.a))
        self.assertEqual(seen, {1, 2, 3, 4, 5}, "union under-covered: %s" % seen)

    def test_range_boundary_inclusive(self):
        # [0:4] is inclusive at both ends (t_inside is_00_to_04): 0 and 4 are in,
        # 5 is out. Covers the whole closed interval across the corpus.
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a.inside(vdc.rangelist(vdc.rng(0, 4)))

        c = C()
        seen = set()
        for i in range(80):
            random.seed(i)
            c.randomize()
            self.assertTrue(0 <= int(c.a) <= 4, int(c.a))
            seen.add(int(c.a))
        self.assertEqual(seen, {0, 1, 2, 3, 4}, "boundary interval not fully covered")

    def test_not_inside_multi_range(self):
        # a<20 and a NOT in {[1:2],[3:5]} : excludes 1..5, keeps the rest of [0,19].
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a < 20
                self.a.not_inside(vdc.rangelist(vdc.rng(1, 2), vdc.rng(3, 5)))

        c = C()
        for i in range(60):
            random.seed(i)
            c.randomize()
            v = int(c.a)
            self.assertLess(v, 20)
            self.assertNotIn(v, (1, 2, 3, 4, 5))

    # ---- x inside {array} : t_inside_unpacked ---------------------------- #
    def test_inside_fixed_table(self):
        # Membership against a fixed (non-rand) lookup table's element set.
        @vdc.dataclass
        class C(vdc.RandClass):
            tbl: list[vdc.u8] = vdc.field(default_factory=lambda: [10, 20, 30, 40])
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.x.inside(vdc.rangelist(self.tbl))

        c = C()
        for i in range(40):
            random.seed(i)
            c.randomize()
            self.assertIn(int(c.x), (10, 20, 30, 40))
            self.assertEqual([int(v) for v in c.tbl], [10, 20, 30, 40])

    def test_inside_rand_array(self):
        # Membership against a *rand* array: x must equal one of the solved elements.
        @vdc.dataclass
        class C(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.arr) as it:
                    it < 50
                self.x.inside(vdc.rangelist(self.arr))

        c = C()
        for i in range(30):
            random.seed(i)
            c.randomize()
            xs = [int(e) for e in c.arr]
            self.assertIn(int(c.x), xs, (int(c.x), xs))

    # ---- reversed / empty range ------------------------------------------ #
    def test_empty_range_unsat(self):
        # A reversed range [5:3] matches nothing (SV: "left of colon > right never
        # matches"), so it is the sole membership option -> UNSAT.
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a.inside(vdc.rangelist(vdc.rng(5, 3)))

        with self.assertRaises(SolveFailure):
            C().randomize()

    def test_empty_range_union_noop(self):
        # An empty range is a no-op inside a union: {[5:3], [3:5]} == {[3:5]}.
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a.inside(vdc.rangelist(vdc.rng(5, 3), vdc.rng(3, 5)))

        c = C()
        for i in range(40):
            random.seed(i)
            c.randomize()
            self.assertIn(int(c.a), (3, 4, 5), int(c.a))
