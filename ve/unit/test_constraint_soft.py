'''
Created on Mar 21, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestConstraintSoft(VscTestCase):
    
    def test_soft_smoke(self):
        
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_lt_b(self):
                vsc.soft(self.a < self.b)
                self.a > 0
                
        my_i = my_cls()
        
        with my_i.randomize_with() as i:
            i.a == i.b
            
        self.assertEqual(i.a, i.b)

        # Should be able to respect the soft constraints        
        with my_i.randomize_with() as i:
            i.a != i.b
            
        self.assertNotEqual(i.a, i.b)
        self.assertLess(i.a, i.b)
        self.assertGreater(i.a, 0)
            
        