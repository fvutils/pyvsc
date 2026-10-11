'''
``~a`` is taken at the expression's context width (SystemVerilog): in
``~a == 0xF0`` with a u8 ``a``, ``a`` is widened to 32 bits before it is
inverted, so the upper bits of ``~a`` are set and the comparison never
holds. dv-solve did this; Boolector inverted ``a`` at 8 bits and found
``a == 15`` (B8).
'''
import vsc
from vsc.model.solve_failure import SolveFailure
from vsc_test_case import VscTestCase


@vsc.randobj
class Inv(object):

    def __init__(self):
        self.a = vsc.rand_uint8_t()


class TestInvertContextWidth(VscTestCase):

    def test_unmasked_is_unsat(self):
        o = Inv()
        with self.assertRaises(SolveFailure):
            with o.randomize_with() as it:
                ~it.a == 0xF0

    def test_masked_to_the_field_width(self):
        o = Inv()
        for _ in range(5):
            with o.randomize_with() as it:
                (~it.a & 0xFF) == 0xF0
            self.assertEqual(o.a, 0x0F)

    def test_against_a_negative_constant(self):
        # ~0x0F at 32 bits is 0xFFFFFFF0, which is -16.
        o = Inv()
        with o.randomize_with() as it:
            ~it.a == -16
        self.assertEqual(o.a, 0x0F)
