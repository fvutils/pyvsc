'''
Dataclass-front-end parallel of ve/unit/test_randomize_with.py.

P1 subset: test_smoke. The classic test_randomize_with_randselect uses standalone
field randomization (vsc.randomize_with(self.value)) + randselect, which lands later.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandomizeWith(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_class(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u16 = vdc.rand()
            c: vdc.u16 = vdc.rand()
            d: vdc.u16 = vdc.rand()

            @vdc.constraint
            def my_a_c(self):
                self.a < 10
                with vdc.if_then(self.a == 2):
                    self.b < 1000
                with vdc.else_then():
                    self.b < 2000

        c = my_class()

        for i in range(1000):
            with c.randomize_with() as it:
                it.a == (i % 10)
            self.assertEqual(it.a, (i % 10))
