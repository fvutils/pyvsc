'''
Dataclass-front-end parallel of ve/unit/test_randomization.py.

P1 subset: test_single (pure randomization). The classic test_simple couples
randomization with a covergroup and lands with Phase 3 (coverage).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandomization(DcTestCase):

    def test_single(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u16 = vdc.rand()
            b: vdc.u16 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < self.b

        my_i = my_s()

        for i in range(100):
            my_i.randomize()
            self.assertLess(my_i.a, my_i.b)
