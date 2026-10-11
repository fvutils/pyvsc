'''
SystemVerilog's rule for an expression with a signed and an unsigned
operand: the expression is unsigned, and a signed operand is zero-extended
(read as its unsigned bit pattern), not sign-extended. Boolector follows it;
dv-solve sign-extended the signed operand (B9), so ``s - b == 3; s < 0``
(s8 ``s``, u8 ``b``) was unsatisfiable there.
'''
import vsc
from vsc_test_case import VscTestCase


def _mk(*body):

    @vsc.randobj
    class M(object):

        def __init__(self):
            self.s = vsc.rand_int8_t()
            self.t = vsc.rand_int8_t()
            self.b = vsc.rand_uint8_t()

        @vsc.constraint
        def c(self):
            for f in body:
                f(self)
    return M()


class TestMixedSignExpr(VscTestCase):

    def _run(self, obj, check, n=20):
        for _ in range(n):
            obj.randomize()
            self.assertTrue(check(obj), (obj.s, obj.t, obj.b))

    def test_difference_is_unsigned(self):
        self._run(_mk(lambda s: s.s - s.b == 3, lambda s: s.s < 0),
                  lambda o: o.s < 0 and ((o.s & 0xFF) - o.b) & 0xFFFFFFFF == 3)

    def test_sum_reads_the_bit_pattern(self):
        self._run(_mk(lambda s: s.s + s.b == 300),
                  lambda o: (o.s & 0xFF) + o.b == 300)

    def test_comparison_is_unsigned(self):
        # -1 is 0xFF unsigned: never below b.
        self._run(_mk(lambda s: s.s < s.b, lambda s: s.s < 0),
                  lambda o: o.s < 0 and (o.s & 0xFF) < o.b)

    def test_equality_reads_the_bit_pattern(self):
        self._run(_mk(lambda s: s.s == s.b, lambda s: s.b > 200),
                  lambda o: (o.s & 0xFF) == o.b and o.s < 0)

    def test_signed_only_stays_signed(self):
        self._run(_mk(lambda s: s.s + s.t == -3, lambda s: s.s < s.t),
                  lambda o: o.s + o.t == -3 and o.s < o.t)

    def test_equality_with_a_wider_unsigned(self):
        # s is zero-extended to 16 bits: -56 (0xC8) equals 200.
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.s = vsc.rand_int8_t()
                self.u = vsc.rand_uint16_t()

            @vsc.constraint
            def c(self):
                self.s == self.u
                self.s < 0

        o = W()
        for _ in range(20):
            o.randomize()
            self.assertEqual(o.s & 0xFF, o.u)
            self.assertLess(o.s, 0)
