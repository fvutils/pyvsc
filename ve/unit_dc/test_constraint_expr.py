'''
Dataclass-front-end parallel of ve/unit/test_constraint_expr.py.

Same scenarios and assertions; only the declaration syntax differs (vdc dataclass
fields + base class instead of vsc.randobj + type_base fields). Constraint bodies
and randomize_with blocks are identical to the classic suite.

Phase 1 scope: scalar comparisons, arithmetic/bitwise ops, part-select, unary not.
The compound-array part-select case (classic test_partselect_compound_array) lands
with Phase 2 (arrays/composites) and is intentionally absent here.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintExpr(DcTestCase):

    def test_eq(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        for i in range(2):
            with my_i.randomize_with() as it:
                it.a == it.b
            self.assertEqual(my_i.a, my_i.b)

    def test_ne(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a != it.b
        self.assertNotEqual(my_i.a, my_i.b)

    def test_gt(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a > it.b
        self.assertGreater(my_i.a, my_i.b)

    def test_ge(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a >= it.b
        self.assertGreaterEqual(my_i.a, my_i.b)

    def test_lt(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a < it.b
        self.assertLess(my_i.a, my_i.b)

    def test_le(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a <= it.b
        self.assertLessEqual(my_i.a, my_i.b)

    def test_eq_rel_sign_ext(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a:  vdc.s8 = vdc.rand()
            eq: vdc.s8 = vdc.rand()
            ne: vdc.s8 = vdc.rand()
            gt: vdc.s8 = vdc.rand()
            ge: vdc.s8 = vdc.rand()
            lt: vdc.s8 = vdc.rand()
            le: vdc.s8 = vdc.rand()

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a == 5
            it.eq == (it.a == 5)
            it.ne == (it.a != 6)
            it.gt == (it.a > 4)
            it.ge == (it.a >= 4)
            it.lt == (it.a < 6)
            it.le == (it.a <= 6)
        self.assertEqual(my_i.eq, 1)
        self.assertEqual(my_i.ne, 1)
        self.assertEqual(my_i.gt, 1)
        self.assertEqual(my_i.ge, 1)
        self.assertEqual(my_i.lt, 1)
        self.assertEqual(my_i.le, 1)

    def test_add(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a + it.b)
        self.assertEqual(my_i.c, (my_i.a + my_i.b))

    def test_sub(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128
                self.a > self.b

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a - it.b)
        self.assertEqual(my_i.c, (my_i.a - my_i.b))

    def test_udiv(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a / it.b)
        self.assertEqual(my_i.c, int(my_i.a / my_i.b))

    def test_sdiv(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.s8 = vdc.rand()
            b: vdc.s8 = vdc.rand()
            c: vdc.s8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < 0
                self.b != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a / it.b)
        self.assertEqual(my_i.c, int(my_i.a / my_i.b))

    def test_mul(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 64
                self.b != 0
                self.b < 4

        my_i = my_c()
        for i in range(100):
            with my_i.randomize_with() as it:
                it.c == (it.a * it.b)
            self.assertEqual(my_i.c, (my_i.a * my_i.b))

    def test_mod(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 8

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a % it.b)
        self.assertEqual(my_i.c, (my_i.a % my_i.b))

    def test_smod(self):
        # SystemVerilog signed %: remainder takes the sign of the dividend.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.s8 = vdc.rand()
            b: vdc.s8 = vdc.rand()
            c: vdc.s8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < 0
                self.b != 0

        def sv_mod(a, b):
            r = abs(a) % abs(b)
            return -r if a < 0 else r

        my_i = my_c()
        for _ in range(20):
            with my_i.randomize_with() as it:
                it.c == (it.a % it.b)
            self.assertEqual(my_i.c, sv_mod(int(my_i.a), int(my_i.b)))

    def test_and(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a & it.b)
        self.assertEqual(my_i.c, (my_i.a & my_i.b))

    def test_or(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a | it.b)
        self.assertEqual(my_i.c, (my_i.a | my_i.b))

    def test_sll(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 4
                self.b != 0
                self.b < 4

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a << it.b)
        self.assertEqual(my_i.c, (my_i.a << my_i.b))

    def test_srl(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a >> it.b)
        self.assertEqual(my_i.c, (my_i.a >> my_i.b))

    def test_xor(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a ^ it.b)
        self.assertEqual(my_i.c, (my_i.a ^ my_i.b))

    def test_slice(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == it.a[1]
        self.assertEqual(my_i.c, (my_i.a & 0x2) >> 1)

    def test_slice2(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0

        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == it.a[2:1]
        self.assertEqual(my_i.c, (my_i.a & 0x6) >> 1)

    def test_unary_not(self):
        @vdc.dataclass
        class Test(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def test_c(self):
                self.a == ~self.b

        inst = Test()
        inst.randomize()
        self.assertEqual(inst.a, ~inst.b & 0xFF)
