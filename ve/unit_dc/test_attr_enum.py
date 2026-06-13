'''
Dataclass-front-end parallel of ve/unit/test_attr_enum.py.

In the dc front-end an enum field is declared by annotating it with the IntEnum/Enum
class directly (``a: my_e = vdc.rand()``); a non-rand enum uses ``vdc.field()``.
'''
from enum import Enum, auto, IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestAttrEnum(DcTestCase):

    def test_rand_plain_enum(self):

        class my_e(Enum):
            A = auto()
            B = auto()

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: my_e = vdc.rand()
            b: my_e = vdc.field()

        inst = my_s()
        for i in range(100):
            inst.randomize()

    def test_rand_int_enum(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: my_e = vdc.rand()
            b: my_e = vdc.field()
            c: vdc.u8 = vdc.rand()

        a_hist = [0] * 2
        inst = my_s()

        for i in range(100):
            if inst.a == my_e.A:
                a_hist[0] += 1
            else:
                a_hist[1] += 1
            inst.randomize()

        delta = abs(a_hist[0] - a_hist[1])
        self.assertLess(delta, 50)
