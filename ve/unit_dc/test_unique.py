'''
Dataclass-front-end parallel of ve/unit/test_unique.py.

P2 scalar subset: test_simple. (test_linked is the same pattern at larger scale;
added here with an explicit uniqueness assertion the classic file only prints.)
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestUnique(DcTestCase):

    def test_simple(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u4 = vdc.rand()
            b: vdc.u4 = vdc.rand()
            c: vdc.u4 = vdc.rand()
            d: vdc.u4 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a != 0
                self.b != 0
                self.c != 0
                self.d != 0

                vdc.unique(self.a, self.b, self.c, self.d)

        v = my_s()
        v.randomize()
        self.assertEqual(len({v.a, v.b, v.c, v.d}), 4)
