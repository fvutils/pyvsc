'''
Dataclass-front-end parallel of ve/unit/test_randomize_with.py.

P1 subset: test_smoke. The classic test_randomize_with_randselect uses standalone
field randomization (vsc.randomize_with(self.value)) + randselect, which lands later.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class _Arrs(vdc.RandClass):
    i: vdc.u8 = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(size=5)
    ra: list[vdc.u8] = vdc.rand(max_size=6)

    @vdc.constraint
    def c(self):
        self.ra.size <= 6


class TestRandomizeWith(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_class(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u16 = vdc.rand()
            c: vdc.u16 = vdc.rand()
            d: vdc.u16 = vdc.rand()

            @vdc.constraint
            def my_a_c(self):
                self.a < 10
                with vdc.if_then(self.a == 2):
                    self.b < 1000
                with vdc.else_then():
                    self.b < 2000

        c = my_class()

        for i in range(1000):
            with c.randomize_with() as it:
                it.a == (i % 10)
            self.assertEqual(it.a, (i % 10))

    def test_array_element(self):
        # B13: it.arr[k] was a bit-select of the array (AttributeError at
        # randomize). Constant and symbolic indices, and a random-size array.
        o = _Arrs()
        for _ in range(20):
            with o.randomize_with() as it:
                it.arr[3] == 77
                it.i < 5
                it.arr[it.i] == 9
                it.ra.size == 4
                it.ra[1] == 3
            self.assertEqual(o.arr[3], 77)
            self.assertEqual(o.arr[o.i], 9)
            self.assertEqual(len(o.ra), 4)
            self.assertEqual(o.ra[1], 3)
        # The object still randomizes on its own afterwards.
        for _ in range(5):
            o.randomize()
            self.assertLessEqual(len(o.ra), 6)

    def test_array_sum(self):
        o = _Arrs()
        for _ in range(10):
            with o.randomize_with() as it:
                it.arr.sum == 100
            self.assertEqual(sum(o.arr), 100)
