'''
Created on Jul 29, 2019

@author: ballance
'''
from unittest.case import TestCase
import vsc

class TestRandomization(TestCase):
                        
    def test_simple(self):
        
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(2)
                self.d = vsc.rand_bit_t(1)
                self.e = vsc.rand_bit_t(16)
                self.f = vsc.rand_bit_t(8)
                self.g = vsc.rand_bit_t(2)
                self.h = vsc.rand_bit_t(1)
                self.i = vsc.rand_bit_t(16)
                self.j = vsc.rand_bit_t(8)
                self.k = vsc.rand_bit_t(2)
                self.l = vsc.rand_bit_t(1)
                
            @vsc.constraint
            def ab_c(self):
               
                with vsc.if_then(self.a < self.b):
                    self.c < self.d
                with vsc.else_then():
                    self.c == self.d
#                self.c != self.d
                pass

        v = my_s()
        
        for i in range(1000):
            vsc.randomize(v)
            
            print("a=" + str(v.a()) + " b=" + str(v.b()) + " c=" + str(v.c()) + " d=" + str(v.d()) + " e=" + str(v.e()) + " f=" + str(v.f()))
        