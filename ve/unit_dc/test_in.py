'''
Dataclass-front-end parallel of ve/unit/test_in.py.

Pins `inside`/`not_inside`/`rangelist` membership — including **variable range
endpoints** (`a inside [rng(c, d)]`, `a inside {b, b+1}`), which was a dc parity gap
(the parser's `_ranges` used to require constant endpoints). Exercises both the
`x in rangelist(...)` operator form and the `x.inside(...)` method form; a literal
endpoint still lowers to a constant exactly as before.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestIn(DcTestCase):

    def test_const_rangelist(self):
        # Constant value-set (control): a in {1,2,4,8}.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a.inside(vdc.rangelist(1, 2, 4, 8))

        v = my_s()
        for _ in range(50):
            v.randomize()
            self.assertIn(int(v.a), (1, 2, 4, 8))

    def test_variable_range(self):
        # a inside [rng(c, d)] with rand c < d — the variable-range gap.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def cc(self):
                self.c != 0
                self.d != 0
                self.c < self.d
                self.a.inside(vdc.rangelist(vdc.rng(self.c, self.d)))

        v = my_s()
        for _ in range(100):
            v.randomize()
            self.assertLess(int(v.c), int(v.d))
            self.assertTrue(int(v.c) <= int(v.a) <= int(v.d))

    def test_variable_value_set_in_operator(self):
        # The `in` operator form with arithmetic over a rand endpoint: a in {b, b+1}.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.b < 200
                self.a in vdc.rangelist(self.b, self.b + 1)

        v = my_s()
        for _ in range(100):
            v.randomize()
            self.assertIn(int(v.a), (int(v.b), int(v.b) + 1))

    def test_not_inside_variable_range(self):
        # not_inside with a variable range: a must avoid [c, d].
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def cc(self):
                self.c == 10
                self.d == 20
                self.a.not_inside(vdc.rangelist(vdc.rng(self.c, self.d)))

        v = my_s()
        for _ in range(100):
            v.randomize()
            self.assertFalse(10 <= int(v.a) <= 20)
