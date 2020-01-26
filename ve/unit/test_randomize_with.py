'''
Created on Dec 23, 2019

@author: ballance
'''
from unittest.case import TestCase
import vsc
from vsc.types import rand_bit_t

class TestRandomizeWith(TestCase):
    
    def test_smoke(self):
        
        class my_class(vsc.RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(16)
                self.c = rand_bit_t(16)
                self.d = rand_bit_t(16)
#                 self.e = rand_bit_t(16)
#                 self.f = rand_bit_t(16)
#                 self.g = rand_bit_t(16)

#            @vsc.constraint
#            def abc_c(self):
#                self
                
            @vsc.constraint
            def my_a_c(self):
                self.a < 10
                with vsc.if_then(self.a == 2):
                    self.b < 1000
                with vsc.else_then():
                    self.b < 2000
                
        c = my_class()

        for i in range(1000):
#            c.randomize()
            with c.randomize_with() as it:
                it.a == (i%10)
        
            print("i=" + str(i) + " c.a=" + hex(c.a) + " c.b=" + hex(c.b) + " c.c=" + hex(c.c) + " c.d=" + hex(c.d))
            