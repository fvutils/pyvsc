'''
Dataclass-front-end adaptation of t_randc_enum_constraint.v.

A randc enum field under a user constraint must only ever produce *valid enum
members* (never an arbitrary bit pattern), cycling through exactly the members the
constraint admits. Covers an exclusion constraint (drop one member) and a range
constraint (keep a prefix of members).
'''
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class color_t(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    WHITE = 3
    BLACK = 4


class TestRandcEnumConstraint(DcTestCase):

    def test_enum_exclusion(self):
        # ColorClass: randc color with color != BLACK -> cycles {RED..WHITE}.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            color: color_t = vdc.randc()

            @vdc.constraint
            def c_no_dark(self):
                self.color != color_t.BLACK

        c = my_c()
        valid = [color_t.RED, color_t.GREEN, color_t.BLUE, color_t.WHITE]
        valid_v = sorted(int(m) for m in valid)
        count = {v: 0 for v in valid_v}
        cycles = 5
        for _ in range(cycles):
            window = []
            for _ in range(len(valid_v)):
                c.randomize()
                self.assertIn(c.color, valid)        # a real member, not 4/BLACK
                self.assertNotEqual(c.color, color_t.BLACK)
                window.append(int(c.color))
                count[int(c.color)] += 1
            self.assertEqual(sorted(window), valid_v)
        for v in valid_v:
            self.assertEqual(count[v], cycles)

    def test_enum_range(self):
        # AllColorsClass: randc color with color <= WHITE keeps {RED..WHITE} and
        # only ever yields valid members.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            color: color_t = vdc.randc()

            @vdc.constraint
            def c_range(self):
                self.color <= color_t.WHITE

        c = my_c()
        valid_v = sorted(int(m) for m in
                         (color_t.RED, color_t.GREEN, color_t.BLUE, color_t.WHITE))
        seen = set()
        for _ in range(40):
            c.randomize()
            self.assertIn(int(c.color), valid_v)
            seen.add(int(c.color))
        # Over many draws the whole admitted set is exercised.
        self.assertEqual(sorted(seen), valid_v)
