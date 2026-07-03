'''
Dataclass-front-end parallel of ve/unit/test_pre_post_randomize.py, extended with
the Verilator prepost corpus: t_randomize_prepost (ordering + super chaining),
t_randomize_prepost_with_baseref (post reads the solved value), and
t_randomize_prepost_nested (inherited/partial/no-super override matrix + recursive
callbacks on 3-level nested rand objects; IEEE 1800-2023 18.4.1).

Semantics pinned:
  - ``pre_randomize`` runs BEFORE the solve (sees fields at their pre-solve state),
    ``post_randomize`` AFTER writeback (sees the solved values, and its edits stick);
  - both are ordinary Python methods, so inheritance and ``super().pre_randomize()``
    chaining follow the MRO — a derived override that omits the ``super`` call does
    NOT invoke the base hook;
  - nested rand-object fields get their own callbacks fired recursively.

Counter/state fields are plain (non-rand) dataclass attributes the solver leaves
alone; the hooks mutate them in Python.
'''
from enum import Enum, auto

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestPrePostRandomize(DcTestCase):

    def test_post_rand_list_mod(self):

        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()

        @vdc.dataclass
        class my_s(vdc.RandClass):
            b: my_e = vdc.rand()
            temp: list = vdc.field(default_factory=list)

            @vdc.constraint
            def ab_c(self):
                self.b in vdc.rangelist(my_e.A, my_e.D)

            def post_randomize(self):
                self.temp.append(self.b)

        my = my_s()

        for i in range(5):
            my.randomize()
            self.assertEqual(len(my.temp), i + 1)


# --- t_randomize_prepost: ordering + super chaining -------------------------
@vdc.dataclass
class Base(vdc.RandClass):
    m_pre: vdc.s32 = 0
    r: vdc.u8 = vdc.rand()
    m_post: vdc.s32 = 0

    @vdc.constraint
    def r_c(self):
        self.r == 20            # RANDOMIZED

    def pre_randomize(self):
        # Runs before the solve: m_pre still 0, m_post still 0.
        assert int(self.m_pre) == 0
        assert int(self.m_post) == 0
        self.m_pre = 10

    def post_randomize(self):
        # Runs after writeback: m_pre set by pre, r solved, m_post still 0.
        assert int(self.m_pre) == 10
        assert int(self.r) == 20
        assert int(self.m_post) == 0
        self.m_post = 30


@vdc.dataclass
class Cls(Base):
    m_cpre: vdc.s32 = 0
    m_cpost: vdc.s32 = 0

    def pre_randomize(self):
        self.m_cpre = 111
        super().pre_randomize()

    def post_randomize(self):
        self.m_cpost = 222
        super().post_randomize()


class TestPrepostOrdering(DcTestCase):

    def test_ordering_and_super_chain(self):
        c = Cls()
        c.randomize()
        self.assertEqual(int(c.m_pre), 10)
        self.assertEqual(int(c.m_cpre), 111)
        self.assertEqual(int(c.r), 20)
        self.assertEqual(int(c.m_post), 30)
        self.assertEqual(int(c.m_cpost), 222)

    def test_ordering_with_inline(self):
        c = Cls()
        with c.randomize_with() as it:
            it.r == 20
        self.assertEqual(int(c.m_pre), 10)
        self.assertEqual(int(c.m_cpre), 111)
        self.assertEqual(int(c.m_post), 30)
        self.assertEqual(int(c.m_cpost), 222)


# --- t_randomize_prepost_with_baseref: post reads the solved value ----------
@vdc.dataclass
class BRBase(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    m_pre: vdc.u8 = 0
    m_post: vdc.u8 = 0


@vdc.dataclass
class BRDerived(BRBase):
    def pre_randomize(self):
        # (Objects are reused across draws here, so m_pre may already be 10 from
        # a prior randomize — pre_randomize is idempotent, always (re)sets 10.)
        self.m_pre = 10

    def post_randomize(self):
        assert int(self.m_pre) == 10
        self.m_post = (int(self.a) + 1) & 0xFF


@vdc.dataclass
class BRBase2(vdc.RandClass):
    b: vdc.u8 = vdc.rand()
    bp: vdc.u8 = 0
    bq: vdc.u8 = 0

    def pre_randomize(self):
        self.bp = 1

    def post_randomize(self):
        self.bq = int(self.b)


@vdc.dataclass
class BRDerived2(BRBase2):
    dp: vdc.u8 = 0
    dq: vdc.u8 = 0

    def pre_randomize(self):
        self.dp = 2
        super().pre_randomize()

    def post_randomize(self):
        self.dq = (int(self.b) + 1) & 0xFF
        super().post_randomize()


class TestPrepostBaseref(DcTestCase):

    def test_post_reads_solved(self):
        d = BRDerived()
        for _ in range(10):
            d.randomize()
            self.assertEqual(int(d.m_pre), 10)
            self.assertEqual(int(d.m_post), (int(d.a) + 1) & 0xFF)

    def test_post_reads_solved_inline(self):
        d = BRDerived()
        with d.randomize_with() as it:
            it.a == 0x3c
        self.assertEqual(int(d.a), 0x3c)
        self.assertEqual(int(d.m_pre), 10)
        self.assertEqual(int(d.m_post), 0x3d)

    def test_super_chain_both_hooks(self):
        d2 = BRDerived2()
        with d2.randomize_with() as it:
            it.b == 0x11
        self.assertEqual(int(d2.b), 0x11)
        self.assertEqual(int(d2.dp), 2)      # derived pre
        self.assertEqual(int(d2.bp), 1)      # base pre via super
        self.assertEqual(int(d2.dq), 0x12)   # derived post
        self.assertEqual(int(d2.bq), 0x11)   # base post via super


# --- t_randomize_prepost_nested: override matrix + recursive callbacks ------
@vdc.dataclass
class BaseInherit(vdc.RandClass):
    x: vdc.s32 = vdc.rand()
    pre_count: vdc.s32 = 0
    post_count: vdc.s32 = 0

    def pre_randomize(self):
        self.pre_count = int(self.pre_count) + 1

    def post_randomize(self):
        self.post_count = int(self.post_count) + 1


@vdc.dataclass
class DerivedNoOverride(BaseInherit):
    y: vdc.s32 = vdc.rand()          # inherits both hooks


@vdc.dataclass
class DerivedPartialOverride(BaseInherit):
    z: vdc.s32 = vdc.rand()
    derived_pre_count: vdc.s32 = 0

    def pre_randomize(self):
        self.derived_pre_count = int(self.derived_pre_count) + 1
        super().pre_randomize()      # chains base pre; post inherited


@vdc.dataclass
class DerivedOverrideBoth(BaseInherit):
    w: vdc.s32 = vdc.rand()
    derived_pre_count: vdc.s32 = 0
    derived_post_count: vdc.s32 = 0

    def pre_randomize(self):
        self.derived_pre_count = int(self.derived_pre_count) + 1   # no super

    def post_randomize(self):
        self.derived_post_count = int(self.derived_post_count) + 1  # no super


@vdc.dataclass
class DerivedOverridePostOnly(BaseInherit):
    v: vdc.s32 = vdc.rand()
    derived_post_count: vdc.s32 = 0

    def post_randomize(self):
        self.derived_post_count = int(self.derived_post_count) + 1  # no super; pre inherited


class TestPrepostOverrideMatrix(DcTestCase):

    def test_inherited_no_override(self):
        o = DerivedNoOverride()
        o.randomize()
        self.assertEqual(int(o.pre_count), 1)
        self.assertEqual(int(o.post_count), 1)

    def test_partial_override_pre(self):
        o = DerivedPartialOverride()
        o.randomize()
        self.assertEqual(int(o.derived_pre_count), 1)
        self.assertEqual(int(o.pre_count), 1)     # super.pre_randomize called
        self.assertEqual(int(o.post_count), 1)    # inherited post

    def test_override_both_no_super(self):
        o = DerivedOverrideBoth()
        o.randomize()
        self.assertEqual(int(o.derived_pre_count), 1)
        self.assertEqual(int(o.derived_post_count), 1)
        self.assertEqual(int(o.pre_count), 0)     # base NOT called
        self.assertEqual(int(o.post_count), 0)

    def test_override_post_only(self):
        o = DerivedOverridePostOnly()
        o.randomize()
        self.assertEqual(int(o.pre_count), 1)          # inherited pre
        self.assertEqual(int(o.derived_post_count), 1)  # overridden post
        self.assertEqual(int(o.post_count), 0)         # base post NOT called


# --- nested 3-level rand objects: each level's callbacks fire ---------------
@vdc.dataclass
class Level3(vdc.RandClass):
    val: vdc.u8 = vdc.rand()
    pre_count: vdc.s32 = 0
    post_count: vdc.s32 = 0

    @vdc.constraint
    def c_val(self):
        self.val in vdc.rangelist((10, 200))

    def pre_randomize(self):
        self.pre_count = int(self.pre_count) + 1

    def post_randomize(self):
        self.post_count = int(self.post_count) + 1


@vdc.dataclass
class Level2(vdc.RandClass):
    l3: Level3 = vdc.rand()
    val: vdc.u8 = vdc.rand()
    pre_count: vdc.s32 = 0
    post_count: vdc.s32 = 0

    @vdc.constraint
    def c_val(self):
        self.val in vdc.rangelist((1, 100))

    def pre_randomize(self):
        self.pre_count = int(self.pre_count) + 1

    def post_randomize(self):
        self.post_count = int(self.post_count) + 1


@vdc.dataclass
class Level1(vdc.RandClass):
    l2: Level2 = vdc.rand()
    val: vdc.u8 = vdc.rand()
    pre_count: vdc.s32 = 0
    post_count: vdc.s32 = 0

    @vdc.constraint
    def c_val(self):
        self.val in vdc.rangelist((50, 150))

    def pre_randomize(self):
        self.pre_count = int(self.pre_count) + 1

    def post_randomize(self):
        self.post_count = int(self.post_count) + 1


class TestPrepostNested(DcTestCase):

    def test_nested_callbacks_fire(self):
        l1 = Level1()
        l1.randomize()
        for obj in (l1, l1.l2, l1.l2.l3):
            self.assertEqual(int(obj.pre_count), 1,
                             "%s pre not fired once" % type(obj).__name__)
            self.assertEqual(int(obj.post_count), 1,
                             "%s post not fired once" % type(obj).__name__)
        # constraints held at every level
        self.assertTrue(50 <= int(l1.val) <= 150)
        self.assertTrue(1 <= int(l1.l2.val) <= 100)
        self.assertTrue(10 <= int(l1.l2.l3.val) <= 200)

    def test_multiple_randomizations_accumulate(self):
        l1 = Level1()
        for i in range(5):
            l1.randomize()
        for obj in (l1, l1.l2, l1.l2.l3):
            self.assertEqual(int(obj.pre_count), 5)
            self.assertEqual(int(obj.post_count), 5)
