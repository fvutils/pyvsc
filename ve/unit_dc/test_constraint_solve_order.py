'''
Dataclass-front-end parallel of ve/unit/test_constraint_solve_order.py.

The classic file's active tests check runtime misuse-detection (solve_order outside
a constraint scope, buried in if_then, non-field args) — artifacts of the
operator-overloading runtime that have no dc analogue (the dc parser validates
solve_order structurally at decoration time; per plan §6 those stay classic-only).
Its model-introspection tests are `disabled_`. Here we assert the *functional*
guarantee: solve_order yields valid solutions under an ordered dependency.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintSolveOrder(DcTestCase):

    def test_order_solves(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                vdc.solve_order(self.a, self.b)
                self.a < self.b
                with vdc.if_then(self.a == 0):
                    self.b < 10

        i = my_c()
        for _ in range(50):
            i.randomize()
            self.assertLess(i.a, i.b)
            if i.a == 0:
                self.assertLess(i.b, 10)
