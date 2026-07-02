'''
Dataclass-front-end parallel of ve/unit/test_constraint_soft.py.

P1/P2 scalar subset: test_soft_smoke. The dist-priority and compound-array soft
cases land with the dist (Phase 2 dist) and array (Phase 2 arrays) work.

Deepened with the soft-semantics matrix adapted from Verilator
t_randomize_soft.v / _soft_relaxation.v / _soft_cross_object.v (IEEE 1800 §18.5.13):
soft-only, last-wins between two soft on one var, independent soft, soft/hard
intersection, hard-overrides-soft, max-compatible-set relaxation, and cross-object
outer-over-inner soft priority.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


# -- cross-object soft priority (module-level so @constraint source is importable) --

@vdc.dataclass
class _SubCfg(vdc.RandClass):
    timeout: vdc.u32 = vdc.rand()
    enabled: vdc.u1 = vdc.rand()

    @vdc.constraint
    def soft_defaults(self):
        vdc.soft(self.timeout == 1000)
        vdc.soft(self.enabled == 0)


@vdc.dataclass
class _ParentCfg(vdc.RandClass):
    enabled: vdc.u1 = vdc.rand()
    sub_a: _SubCfg = vdc.rand()

    @vdc.constraint
    def soft_defaults(self):
        vdc.soft(self.enabled == 0)

    @vdc.constraint
    def propagate_cons(self):
        with vdc.if_then(self.enabled == 1):
            self.sub_a.enabled == 1


@vdc.dataclass
class _TopTest(vdc.RandClass):
    cfg: _ParentCfg = vdc.rand()
    extra_cfg: _SubCfg = vdc.rand()

    @vdc.constraint
    def cfg_hard_cons(self):
        self.cfg.enabled == 1

    @vdc.constraint
    def cfg_soft_cons(self):
        vdc.soft(self.cfg.sub_a.timeout == 5000)
        vdc.soft(self.extra_cfg.timeout == 9999)
        vdc.soft(self.extra_cfg.enabled == 1)


class TestConstraintSoft(DcTestCase):

    def test_soft_smoke(self):

        @vdc.dataclass
        class my_cls(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def a_lt_b(self):
                vdc.soft(self.a < self.b)
                self.a > 0

        my_i = my_cls()

        with my_i.randomize_with() as i:
            i.a == i.b

        self.assertEqual(my_i.a, my_i.b)

        # Should be able to respect the soft constraints
        with my_i.randomize_with() as i:
            i.a != i.b

        self.assertNotEqual(my_i.a, my_i.b)
        self.assertLess(my_i.a, my_i.b)
        self.assertGreater(my_i.a, 0)

    # -- t_randomize_soft.v case matrix ------------------------------------

    def test_soft_only(self):
        # Case 1: only soft, no conflicting hard -> soft is satisfied.
        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_soft(self):
                vdc.soft(self.x == 5)

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertEqual(int(c.x), 5)

    def test_soft_last_wins(self):
        # Case 2: two soft on the same var -> the later-declared one wins.
        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_a(self):
                vdc.soft(self.x == 5)

            @vdc.constraint
            def c_b(self):
                vdc.soft(self.x == 10)

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertEqual(int(c.x), 10)

    def test_soft_independent_vars(self):
        # Case 3: soft on different vars -> both satisfied.
        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_x(self):
                vdc.soft(self.x == 7)

            @vdc.constraint
            def c_y(self):
                vdc.soft(self.y == 3)

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertEqual(int(c.x), 7)
            self.assertEqual(int(c.y), 3)

    def test_soft_hard_intersection(self):
        # Case 4: soft range partially covered by a hard range -> the soft
        # relaxes to the intersection (x in [5,10]).
        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_soft(self):
                vdc.soft(self.x.inside(vdc.rangelist(vdc.rng(1, 10))))

            @vdc.constraint
            def c_hard(self):
                self.x.inside(vdc.rangelist(vdc.rng(5, 15)))

        c = C()
        for _ in range(50):
            c.randomize()
            self.assertTrue(5 <= int(c.x) <= 10, int(c.x))

    def test_soft_overridden_by_hard(self):
        # Case 5: soft fully contradicted by hard -> hard wins, soft dropped.
        @vdc.dataclass
        class C(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_soft(self):
                vdc.soft(self.x == 5)

            @vdc.constraint
            def c_hard(self):
                self.x > 10

        c = C()
        for _ in range(50):
            c.randomize()
            self.assertGreater(int(c.x), 10)
            self.assertNotEqual(int(c.x), 5)

    # -- t_randomize_soft_relaxation.v -------------------------------------

    def test_soft_relaxation_max_compatible(self):
        # A lower-priority soft that is COMPATIBLE with the winning soft must be
        # kept when a mid-priority soft is dropped for conflicting with the
        # highest-priority one. soft0 (b>100) and soft2 (a==80) both survive;
        # soft1 (a==30) is dropped. Guards the max-compatible-set relaxation.
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_hard(self):
                self.a < 200
                self.b < 200

            @vdc.constraint
            def c_soft0(self):
                vdc.soft(self.b > 100)

            @vdc.constraint
            def c_soft1(self):
                vdc.soft(self.a == 30)

            @vdc.constraint
            def c_soft2(self):
                vdc.soft(self.a == 80)

        c = C()
        for _ in range(20):
            c.randomize()
            self.assertEqual(int(c.a), 80)                 # highest-priority soft
            self.assertTrue(101 <= int(c.b) <= 199, int(c.b))  # compatible soft kept

    # -- t_randomize_soft_cross_object.v -----------------------------------

    def test_soft_cross_object_priority(self):
        # An outer-scope soft (declared on the enclosing object) outranks an
        # inner-scope soft default on the child: the child's `soft timeout==1000`
        # yields to the parent's `soft timeout==5000`/`==9999`.
        t = _TopTest()
        for _ in range(10):
            t.randomize()
            self.assertEqual(int(t.cfg.enabled), 1)              # hard
            self.assertEqual(int(t.cfg.sub_a.timeout), 5000)     # outer soft wins
            self.assertEqual(int(t.extra_cfg.timeout), 9999)     # outer soft wins

    def test_soft_wide_field(self):
        # Regression: a soft constraint reifies its expression, and the dv-solve
        # primary engine's reified comparison is 32-bit only, so a soft over a
        # tier-1-wide field (unsigned width >= 32) used to infinite-loop / drop the
        # soft. Now routed to the complete BV-SAT engine. Cover u32/u48/u64 and
        # each comparison op; assert the soft is honored (not merely non-hanging).
        for T in (vdc.u32, vdc.u48, vdc.u64):
            @vdc.dataclass
            class C(vdc.RandClass):
                x: T = vdc.rand()

                @vdc.constraint
                def c_soft(self):
                    vdc.soft(self.x == 5)

            c = C()
            for _ in range(10):
                c.randomize()
                self.assertEqual(int(c.x), 5)

        # Inequality soft over a wide field is honored too (previously silently
        # dropped, returning an out-of-range value).
        @vdc.dataclass
        class D(vdc.RandClass):
            x: vdc.u32 = vdc.rand()

            @vdc.constraint
            def c_soft(self):
                vdc.soft(self.x < 100)

        d = D()
        for _ in range(20):
            d.randomize()
            self.assertLess(int(d.x), 100)
