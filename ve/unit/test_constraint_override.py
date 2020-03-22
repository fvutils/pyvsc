'''
Created on Mar 21, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestConstraintOverride(VscTestCase):
    
    def test_basics(self):
        
        @vsc.randobj
        class my_base_s(object):
            
            def __init__(self):
                self.a = vsc.rand_uint16_t()
                self.b = vsc.rand_uint16_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a < self.b
                
        @vsc.randobj
        class my_ext_s(my_base_s):
            
            def __init__(self):
                super().__init__()
                self.c = vsc.rand_uint16_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a > self.b
                
            @vsc.constraint
            def ac_c(self):
                self.c == self.a

        base = my_base_s()
 
        for i in range(100):
            base.randomize()
            self.assertLess(base.a, base.b)
            
        ext = my_ext_s()
        for i in range(100):
            ext.randomize()
            self.assertGreater(ext.a, ext.b)
            self.assertEqual(ext.a, ext.c)
            
