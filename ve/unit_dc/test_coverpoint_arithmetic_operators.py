'''
Dataclass-front-end parallel of ve/unit/test_coverpoint_arithmetic_operators.py.

Classic covers an arithmetic *expression* (``coverpoint(self.a * self.b, ...)``).
In dc this is just a pull coverpoint whose ref lambda computes the expression from
sample_arg state — no special support needed.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestCoverpointArithmetic(DcTestCase):

    def test_multiplication(self):

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.u8 = vdc.sample_arg()
            b: vdc.u8 = vdc.sample_arg()
            prod_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.a * s.b,
                bins=dict(prod=vdc.bin_array([], 1, 2, 4, 12)))

        cg = my_cg()
        cg.sample(2, 6)     # 12 -> bin
        cg.sample(1, 1)     # 1  -> bin
        self.assertEqual(cg.prod_cp.get_coverage(), 50)   # 2 of 4 value bins

    def test_addition_and_shift(self):

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.u8 = vdc.sample_arg()
            b: vdc.u8 = vdc.sample_arg()
            sum_cp: vdc.Coverpoint[vdc.u16] = vdc.coverpoint(
                lambda s: s.a + s.b,
                bins=dict(s=vdc.bin_array([], 3, 7, 15)))
            shift_cp: vdc.Coverpoint[vdc.u16] = vdc.coverpoint(
                lambda s: s.a << 1,
                bins=dict(sh=vdc.bin_array([], 4, 8)))

        cg = my_cg()
        cg.sample(1, 2)     # sum 3, shift 2
        cg.sample(2, 2)     # sum 4 (no bin), shift 4
        self.assertGreater(cg.sum_cp.get_coverage(), 0.0)
        self.assertGreater(cg.shift_cp.get_coverage(), 0.0)
