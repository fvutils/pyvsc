'''
Dataclass-front-end parallel of ve/unit/test_constraint_soft.py.

P1/P2 scalar subset: test_soft_smoke. The dist-priority and compound-array soft
cases land with the dist (Phase 2 dist) and array (Phase 2 arrays) work.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintSoft(DcTestCase):

    def test_soft_smoke(self):

        @vdc.dataclass
        class my_cls(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def a_lt_b(self):
                vdc.soft(self.a < self.b)
                self.a > 0

        my_i = my_cls()

        with my_i.randomize_with() as i:
            i.a == i.b

        self.assertEqual(my_i.a, my_i.b)

        # Should be able to respect the soft constraints
        with my_i.randomize_with() as i:
            i.a != i.b

        self.assertNotEqual(my_i.a, my_i.b)
        self.assertLess(my_i.a, my_i.b)
        self.assertGreater(my_i.a, 0)
