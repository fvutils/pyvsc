'''
Dataclass-front-end parallel of ve/unit/test_constraint_mode.py.

Classic spells constraint enable/disable as ``it.<cname>.constraint_mode(en)``.
In dc, fields are plain values and constraint methods are plain methods, so the
toggle is a method keyed by the constraint name: ``obj.set_constraint_mode(name,
enabled)`` (mirrors ``set_rand_mode``). Same scenarios, same assertions.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintMode(DcTestCase):

    def test_constraint_mode(self):

        @vdc.dataclass
        class my_item_1_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_eq_c(self):
                self.a == self.b

            @vdc.constraint
            def ab_ne_c(self):
                self.a != self.b

        it = my_item_1_c()

        for _ in range(16):
            it.set_constraint_mode("ab_eq_c", True)
            it.set_constraint_mode("ab_ne_c", False)
            it.randomize()
            self.assertEqual(it.a, it.b)

            it.set_constraint_mode("ab_eq_c", False)
            it.set_constraint_mode("ab_ne_c", True)
            it.randomize()
            self.assertNotEqual(it.a, it.b)

    def test_bounds_smoke(self):
        # Bounds must be re-derived when a constraint is disabled: a_zero_c would
        # pin a==0, but disabled, 0 is nigh-impossible over 1024 bits.
        # See: https://github.com/fvutils/pyvsc/issues/173

        @vdc.dataclass
        class my_item_0_c(vdc.RandClass):
            a: vdc.bitv = vdc.rand(width=1024)

            @vdc.constraint
            def a_zero_c(self):
                self.a == 0

        it = my_item_0_c()
        it.set_constraint_mode("a_zero_c", False)

        for _ in range(16):
            it.randomize()
            self.assertNotEqual(it.a, 0)
