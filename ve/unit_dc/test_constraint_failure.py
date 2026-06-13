'''
Dataclass-front-end parallel of ve/unit/test_constraint_failure.py.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.model.solve_failure import SolveFailure


class TestConstraintFailure(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a > 5
                self.b < 5
                self.a < self.b

        it = my_c()

        try:
            it.randomize()
            self.fail("no exception thrown")
        except SolveFailure as e:
            pass
