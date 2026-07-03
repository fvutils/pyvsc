'''
Dataclass-front-end adaptation of the Verilator "smoke" corpus: t_randomize,
t_randomize_method, t_randomize_method_constraints, t_randomize_method_std.

These are broad end-to-end sanity classes rather than single-feature probes: a
Packet combining most constraint shapes at once (empty block, if/else, foreach +
unique, dist, solve-before), an inheritance + nested-object + non-rand-preserved
matrix, wide-field arithmetic/membership/part-select constraints, and
randomize-in-constructor.

Tier-3 drops (no dc equivalent): ``disable soft`` (the dis block collapses to the
plain ``sublength <= length``); reduction-or ``|redor`` (expressed via the
equivalent part-select ``redor[31:1]==0 && redor[0]==1``); packed structs modelled
as nested dataclasses; ``local::if_4`` modelled as a captured Python constant.
'''
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class Enum16(IntEnum):
    ONE = 3
    TWO = 5
    THREE = 8
    FOUR = 13


# --- t_randomize: one Packet exercising most constraint shapes at once ------
@vdc.dataclass
class Packet(vdc.RandClass):
    header: vdc.u32 = vdc.rand()      # 1..7
    length: vdc.u32 = vdc.rand()      # header..15
    sublength: vdc.u32 = vdc.rand()
    if_4: vdc.u1 = vdc.rand()
    iff_5_6: vdc.u1 = vdc.rand()
    array: list[vdc.u32] = vdc.rand(size=2)

    @vdc.constraint
    def empty(self):
        pass                          # empty constraint block is a no-op

    @vdc.constraint
    def size(self):
        self.header > 0
        self.header <= 7
        self.length <= 15
        self.length >= self.header
        vdc.dist(self.length, [
            vdc.weight(vdc.rng(0, 1), 1),
            vdc.weight(vdc.rng(2, 5), 2),
            vdc.weight(6, 6),
            vdc.weight(7, 10)])

    @vdc.constraint
    def ifs(self):
        with vdc.if_then(self.header > 4):
            self.if_4 == 1
        with vdc.if_then((self.header == 5) | (self.header == 6)):
            self.iff_5_6 == 1
        with vdc.else_then():
            self.iff_5_6 == 0

    @vdc.constraint
    def arr_uniq(self):
        with vdc.foreach(self.array) as it:
            it in vdc.rangelist(2, 4, 6)
        vdc.unique(self.array[0], self.array[1])

    @vdc.constraint
    def order(self):
        vdc.solve_order(self.length, self.header)

    @vdc.constraint
    def dis(self):
        self.sublength <= self.length   # 'disable soft' collapses to the hard rel


class TestRandomizeSmoke(DcTestCase):

    def test_packet_all_shapes(self):
        p = Packet()
        seen = set()
        for _ in range(40):
            p.randomize()
            h = int(p.header)
            self.assertTrue(1 <= h <= 7)
            self.assertTrue(h <= int(p.length) <= 15)
            self.assertLessEqual(int(p.sublength), int(p.length))
            if h > 4:
                self.assertEqual(int(p.if_4), 1)
            if h in (5, 6):
                self.assertEqual(int(p.iff_5_6), 1)
            else:
                self.assertEqual(int(p.iff_5_6), 0)
            self.assertTrue(all(int(a) in (2, 4, 6) for a in p.array))
            self.assertNotEqual(int(p.array[0]), int(p.array[1]))   # unique
            seen.add((h, int(p.length)))
        self.assertGreater(len(seen), 1)

    def test_packet_inline_empty_and_pinned(self):
        p = Packet()
        # empty inline `with {}` — no added constraints, still solves.
        p.randomize()
        # inline pin: if_4 == captured const, header == 2 (local::if_4 analogue).
        if_4_val = 0
        for _ in range(10):
            with p.randomize_with() as it:
                it.if_4 == if_4_val
                it.header == 2
            self.assertEqual(int(p.header), 2)
            self.assertEqual(int(p.if_4), if_4_val)


# --- t_randomize_method: inheritance + nested obj + non-rand preserved ------
@vdc.dataclass
class Inner(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u16 = vdc.rand()
    c: vdc.u4 = vdc.rand()
    d: vdc.u12 = vdc.rand()
    e: vdc.u32 = 0                    # non-rand: must stay 0


@vdc.dataclass
class BaseCls1(vdc.RandClass):
    pass                             # no rand fields (SV BaseCls1)


@vdc.dataclass
class DerivedCls1(BaseCls1):
    i: Inner = vdc.rand()
    j: vdc.s32 = vdc.rand()
    k: vdc.s32 = 0                   # non-rand: must stay 0
    l: Enum16 = vdc.rand()


@vdc.dataclass
class ContainsNull(vdc.RandClass):
    b: BaseCls1 = vdc.rand()         # composite with no rand fields (SV null-ish)


class TestRandomizeMethod(DcTestCase):

    def test_inheritance_nested_nonrand(self):
        d = DerivedCls1()
        moved = {name: False for name in ("a", "b", "c", "j", "l")}
        prev = None
        for _ in range(10):
            d.randomize()
            # non-rand fields stay 0
            self.assertEqual(int(d.i.e), 0)
            self.assertEqual(int(d.k), 0)
            # enum in range
            self.assertIn(int(d.l), [e.value for e in Enum16])
            cur = (int(d.i.a), int(d.i.b), int(d.i.c), int(d.j), int(d.l))
            if prev is not None:
                for idx, name in enumerate(("a", "b", "c", "j", "l")):
                    if cur[idx] != prev[idx]:
                        moved[name] = True
            prev = cur
        self.assertTrue(all(moved.values()),
                        "some rand field never varied: %s" % moved)

    def test_contains_null_composite(self):
        # A rand composite field with no rand members still randomizes cleanly.
        c = ContainsNull()
        for _ in range(5):
            c.randomize()


# --- t_randomize_method_constraints: wide fields + membership/part-select ---
@vdc.dataclass
class WideCls(vdc.RandClass):
    u: vdc.bitv = vdc.rand(width=80)
    v: Enum16 = vdc.rand()
    w: vdc.u64 = vdc.rand()
    x: vdc.bitv = vdc.rand(width=48)
    y: vdc.u32 = vdc.rand()
    z: vdc.bitv = vdc.rand(width=23)
    redor: vdc.u32 = vdc.rand()

    @vdc.constraint
    def A(self):
        self.v in vdc.rangelist(Enum16.ONE, Enum16.THREE)

    @vdc.constraint
    def B(self):
        self.w == 5
        (self.x in vdc.rangelist(1, 2)) | (self.x in vdc.rangelist(4, 5))

    @vdc.constraint
    def C(self):
        self.z < 3 * 7          # 21
        self.z > 5 + 8          # 13
        self.u > 0

    @vdc.constraint
    def D(self):
        # |redor == 1 && redor[31:1] == 0  <=>  redor == 1
        self.redor[31:1] == 0
        self.redor[0] == 1


class TestRandomizeMethodConstraints(DcTestCase):

    def test_wide_constraints(self):
        obj = WideCls()
        for _ in range(25):
            obj.randomize()
            self.assertIn(int(obj.v), (Enum16.ONE, Enum16.THREE))
            self.assertEqual(int(obj.w), 5)
            self.assertIn(int(obj.x), (1, 2, 4, 5))
            self.assertTrue(13 < int(obj.z) < 21)
            self.assertGreater(int(obj.u), 0)
            self.assertEqual(int(obj.redor), 1)


# --- t_randomize_method_std: randomize() in the constructor -----------------
@vdc.dataclass
class CtorRand(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def a_c(self):
        self.a < 100

    def __post_init__(self):
        # Randomizing during construction must succeed (SV: new() calls randomize()).
        self.randomize()


class TestRandomizeInCtor(DcTestCase):

    def test_randomize_in_post_init(self):
        c = CtorRand()
        self.assertLess(int(c.a), 100)
