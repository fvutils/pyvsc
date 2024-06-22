from enum import auto, Enum

from vsc_test_case import VscTestCase


class TestConstraintFunctions(VscTestCase):
    
    def test_clog2(self):
        import vsc

        def clog2(lhs, rhs, nbits):
            with vsc.implies((rhs >= 0) & (rhs < 2)):
                lhs == 0
            for i in range(1,nbits):
                with vsc.implies(((rhs-1) >= (2**(i-1))) & ((rhs-1) < (2**i))):
                    lhs == i

        @vsc.randobj
        class C(object):

            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def clog2_c(self):
                clog2(self.a, self.b, 8)

        c = C()

        for i in range(256):
            with c.randomize_with():
                c.b == i
            print("a=%d b=%d" % (c.a, c.b))

