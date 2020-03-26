'''
Created on Mar 26, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestDynamicConstraint(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a <= 100
                
            @vsc.dynamic_constraint
            def a_small(self):
                self.a in vsc.rangelist([1,10])
                
            @vsc.dynamic_constraint
            def a_large(self):
                self.a in vsc.rangelist([90,100])
                
        my_i = my_cls()

        for i in range(20):        
            with my_i.randomize_with() as it:
                it.a_small()
            print("a=" + str(my_i.a))
            self.assertGreaterEqual(my_i.a, 1)
            self.assertLessEqual(my_i.a, 10)
        
            with my_i.randomize_with() as it:
                it.a_large()
            print("a=" + str(my_i.a))
            self.assertGreaterEqual(my_i.a, 90)
            self.assertLessEqual(my_i.a, 100)
            
