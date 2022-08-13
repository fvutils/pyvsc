
import time
import vsc2 as vsc
from .vsc_test_case2 import VscTestCase2

class TestRandclassBasics(VscTestCase2):
    
    def test_smoke(self):

        @vsc.randclass
        class my_c(object):
            a : vsc.rand_uint8_t
            b : vsc.rand_uint8_t
            c : vsc.rand_uint8_t
            d : vsc.rand_uint8_t
            e : vsc.rand_uint8_t
            f : vsc.rand_uint8_t
    
        c = my_c()
        count = 1000
        start_ms = int(time.time()*1000)
        for _ in range(count):
            c.randomize()
        end_ms = int(time.time()*1000)
        print("%d items in %smS: %0.2fmS/item" % (
            count, (end_ms-start_ms), ((end_ms-start_ms)/count)))

    def test_simple_constraint(self):

        @vsc.randclass
        class my_c(object):
            a : vsc.rand_uint8_t
            b : vsc.rand_uint8_t
            
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.a < self.b
    
        c = my_c()
        count = 1000
        start_ms = int(time.time()*1000)
        for _ in range(count):
            c.randomize()
            self.assertLess(c.a, c.b)
#            print("c.a=%d ; c.b=%d" % (c.a, c.b))            
        end_ms = int(time.time()*1000)
        print("%d items in %smS: %0.2fmS/item" % (
            count, (end_ms-start_ms), ((end_ms-start_ms)/count)))
        