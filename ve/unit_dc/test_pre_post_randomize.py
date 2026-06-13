'''
Dataclass-front-end parallel of ve/unit/test_pre_post_randomize.py.

post_randomize runs after the solve and sees the randomized values; here it
appends the solved enum to a plain (opaque) list field. The classic uses
vsc.list_t state; in dc that is an ordinary ``list`` field the solver ignores.
'''
from enum import Enum, auto

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestPrePostRandomize(DcTestCase):

    def test_post_rand_list_mod(self):

        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()

        @vdc.dataclass
        class my_s(vdc.RandClass):
            b: my_e = vdc.rand()
            temp: list = vdc.field(default_factory=list)

            @vdc.constraint
            def ab_c(self):
                self.b in vdc.rangelist(my_e.A, my_e.D)

            def post_randomize(self):
                self.temp.append(self.b)

        my = my_s()

        for i in range(5):
            my.randomize()
            self.assertEqual(len(my.temp), i + 1)
