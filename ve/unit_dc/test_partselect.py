'''
Dataclass-front-end parallel of ve/unit/test_partselect.py.

Pins **bit part-select inside `@vdc.constraint` methods** — `self.a[hi:lo]` and the
array-element form `self.arr[i][hi:lo]`. This was a dc parity gap (the parser used to
reject slices in `@constraint` bodies with "not yet supported"; part-select worked only
in the inline `randomize_with` path). The classic file's `test_array_elem_bitselect`
exercises *value-side* bit access on a non-rand list; the dc-relevant capability is the
constraint-side part-select, which these tests cover.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestPartSelect(DcTestCase):

    def test_scalar_partselect(self):
        # Constrain the two nibbles of an 8-bit field independently.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a[3:0] == 5      # low nibble
                self.a[7:4] == 2      # high nibble

        v = my_s()
        for _ in range(50):
            v.randomize()
            self.assertEqual(int(v.a) & 0xF, 5)
            self.assertEqual((int(v.a) >> 4) & 0xF, 2)
            self.assertEqual(int(v.a), 0x25)

    def test_partselect_relation(self):
        # A relation between two part-selects of the same field.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u16 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a[15:8] == self.a[7:0]   # high byte == low byte

        v = my_s()
        for _ in range(50):
            v.randomize()
            self.assertEqual((int(v.a) >> 8) & 0xFF, int(v.a) & 0xFF)

    def test_array_elem_partselect(self):
        # Part-select of an array element inside a constraint.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand(size=3)

            @vdc.constraint
            def c(self):
                self.l[0][3:0] == 7
                self.l[1][7:4] == 0xA

        v = my_s()
        for _ in range(50):
            v.randomize()
            self.assertEqual(int(v.l[0]) & 0xF, 7)
            self.assertEqual((int(v.l[1]) >> 4) & 0xF, 0xA)

    def test_single_bit_select(self):
        # A one-bit select (single index) on a scalar in a constraint.
        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a[0] == 1        # force odd
                self.a[7] == 1        # force top bit set

        v = my_s()
        for _ in range(50):
            v.randomize()
            self.assertEqual(int(v.a) & 1, 1)
            self.assertEqual((int(v.a) >> 7) & 1, 1)
