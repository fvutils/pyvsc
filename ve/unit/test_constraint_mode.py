'''
Created on Mar 3, 2020

@author: ballance
'''
import vsc
from unittest.case import TestCase

class TestConstraintMode(TestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_eq_c(self):
                self.a == self.b
                
            @vsc.constraint
            def ab_ne_c(self):
                self.a != self.b
                
        it = my_item_c()

        for i in range(16):        
            it.ab_eq_c.constraint_mode(True)
            it.ab_ne_c.constraint_mode(False)
            it.randomize()
            self.assertEqual(it.a, it.b)
            
            it.ab_eq_c.constraint_mode(False)
            it.ab_ne_c.constraint_mode(True)
            it.randomize()
            self.assertNotEqual(it.a, it.b)
                
                