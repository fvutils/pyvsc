'''
Dataclass-front-end parallel of ve/unit/test_implies.py.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestImplies(DcTestCase):

    def test_simple(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a == 5

                with vdc.implies(self.a == 1):
                    self.b == 1

                with vdc.implies(self.a == 2):
                    self.b == 2

                with vdc.implies(self.a == 3):
                    self.b == 4

                with vdc.implies(self.a == 4):
                    self.b == 8

                with vdc.implies(self.a == 5):
                    self.b == 16

        v = my_s()

        v.randomize()

        self.assertEqual(v.a, 5)
        self.assertEqual(v.b, 16)
