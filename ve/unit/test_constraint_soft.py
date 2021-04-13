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
            
        print("a=" + str(my_i.a) + " b=" + str(my_i.b))
            
        self.assertEqual(my_i.a, my_i.b)

        # Should be able to respect the soft constraints        
        with my_i.randomize_with() as i:
            i.a != i.b
            
        print("a=" + str(my_i.a) + " b=" + str(my_i.b))
            
        self.assertNotEqual(my_i.a, my_i.b)
        self.assertLess(my_i.a, my_i.b)
        self.assertGreater(my_i.a, 0)
        
    def test_soft_dist(self):
        
        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                self.a < self.b
                vsc.soft(self.a > 5) #A
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  10),
                    vsc.weight(1,  100),
                    vsc.weight(2,  10),
                    vsc.weight(4,  10),
                    vsc.weight(8, 10)])

        item = my_item()
        for i in range(10):
            with item.randomize_with() as it:
                it.b > 10
                it.a == 1 #B
            
        