'''
Created on Aug 20, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestConstraintSolveOrder(VscTestCase):
    
    def test_depth_insufficient(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                vsc.solve_order(self.a, self.b)


        try:
            i = my_c()
            self.fail("Failed to detect solve_order outside constraint")
        except Exception:
            pass
                
    def test_depth_excessive(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.b == 10
                    vsc.solve_order(self.a, self.b)                

        try:
            i = my_c()
            self.fail("Failed to detect solve_order buried in a constraint")
        except Exception:
            pass
        
    def test_incorrect_args(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(1, self.b)
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        try:
            i = my_c()
            self.fail("Failed to detect solve_order incorrect arguments")
        except Exception as e:
            print("Exception: " + str(e))
            pass

    def test_simple(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        i = my_c()
