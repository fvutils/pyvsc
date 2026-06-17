'''
Enum-element arrays for the dataclass front-end: a ``list[MyEnum]`` field builds
EnumFieldModel elements (constrained to the enum's values) and writes back enum
members. Fixed-size, random-size, foreach, and indexed access.
'''
from enum import IntEnum, auto

from dc_test_case import DcTestCase
import vsc.dc as vdc


class Color(IntEnum):
    RED = 0
    GREEN = auto()
    BLUE = auto()


class TestListEnum(DcTestCase):

    def test_fixed_foreach(self):

        @vdc.dataclass
        class C(vdc.RandClass):
            cols: list[Color] = vdc.rand(size=4)

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.cols) as it:
                    it != Color.GREEN

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertEqual(len(c.cols), 4)
            self.assertTrue(all(isinstance(x, Color) for x in c.cols))
            self.assertTrue(all(x in (Color.RED, Color.BLUE) for x in c.cols))

    def test_indexed_constraint(self):

        @vdc.dataclass
        class C(vdc.RandClass):
            cols: list[Color] = vdc.rand(size=3)

            @vdc.constraint
            def c(self):
                self.cols[0] == Color.BLUE
                self.cols[1] == self.cols[2]

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertEqual(c.cols[0], Color.BLUE)
            self.assertEqual(c.cols[1], c.cols[2])

    def test_random_size(self):

        @vdc.dataclass
        class C(vdc.RandClass):
            cols: list[Color] = vdc.rand(max_size=8)

            @vdc.constraint
            def c(self):
                self.cols.size > 2
                self.cols.size < 5

        c = C()
        for _ in range(10):
            c.randomize()
            self.assertTrue(2 < len(c.cols) < 5)
            self.assertTrue(all(isinstance(x, Color) for x in c.cols))
