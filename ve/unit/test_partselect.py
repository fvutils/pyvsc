'''
Created on Jul 28, 2019

@author: ballance
'''

from unittest import TestCase
import vsc

class TestPartSelect(TestCase):

    def test_simple(self):
        
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(32)
                self.b = vsc.rand_bit_t(32)
                self.c = vsc.rand_bit_t(32)
                self.d = vsc.rand_bit_t(32)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a[7:3] != 0
                self.a[4] != 0
                self.b != 0
                self.c != 0
                self.d != 0
                
                vsc.unique(self.a, self.b, self.c, self.d)

        v = my_s()
        vsc.randomize(v)
        
        print("a=" + str(v.a()) + " b=" + str(v.b()) + " c=" + str(v.c()) + " d=" + str(v.d()))