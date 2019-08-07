'''
Created on Aug 4, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase
from vsc import *

class TestCovergroup(TestCase):
    
    def test_simple_coverpoint(self):
        
        class my_covergroup(covergroup):
            
            def __init__(self):
                self.cp1 = coverpoint(bit_t(4), bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })
                
        cg = my_covergroup()
        cg.init_model()
        
        cg.cp1 <= 5
        cg.sample()
        cg.cp1 <= 4
        cg.sample()
        cg.cp1 <= 4
        cg.sample()
        
        cg.dump()
        
    def test_class_covergroup(self):
       
        @rand_obj
        class my_rand():
            
            def __init__(self):
                self.a = rand_bit_t(4)
                self.b = rand_bit_t(4)
        
        class my_covergroup(covergroup):
            
            def __init__(self):
                self.cls = my_rand()
                self.cp1 = coverpoint(self.cls.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                
        cg = my_covergroup()
        cg.init_model()

        cg.cls.a.set_val(4)
        cg.sample()
        
        cg.dump()        