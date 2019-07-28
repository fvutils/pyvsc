'''
Created on Jul 28, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase
import vsc


class TestIn(TestCase):
    
    def test_single(self):
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
#                self.a in vsc.rangelist(self.b+1, [self.b+2,self.c], 8)
                self.a in vsc.rangelist(1, 2, 4, 8)
                
#                 with vsc.implies(self.a == 1):
#                     self.b == 1
#                      
#                 with vsc.implies(self.a == 2):
#                     self.b == 2
#                      
#                 with vsc.implies(self.a == 3):
#                     self.b == 4
#                      
#                 with vsc.implies(self.a == 4):
#                     self.b == 8
#                      
#                 with vsc.implies(self.a == 5):
#                     self.b == 16

        v = my_s()
        vsc.randomize(v)    
        
        print("a=" + str(v.a()) + " b=" + str(v.b()))        
        