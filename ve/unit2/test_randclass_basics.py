
import vsc2 as vsc
from .vsc_test_case2 import VscTestCase2

class TestRandclassBasics(VscTestCase2):
    
    def test_smoke(self):

        @vsc.randclass
        class my_c(object):
            a : vsc.rand_uint8_t
            b : vsc.rand_uint8_t
    
        c = my_c()
        for _ in range(10):
            c.randomize()
            print("c.a=%d ; c.b=%d" % (c.a, c.b))