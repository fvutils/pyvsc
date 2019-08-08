
#   Copyright 2019 Matthew Ballance
#   All Rights Reserved Worldwide
#
#   Licensed under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in
#   compliance with the License.  You may obtain a copy of
#   the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in
#   writing, software distributed under the License is
#   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, either express or implied.  See
#   the License for the specific language governing
#   permissions and limitations under the License.

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
        
    def test_simple_cross(self):
       
        class my_covergroup(covergroup):
            
            def __init__(self):
                self.cp1 = coverpoint(bit_t(4), bins={
                    "a" : bin_array([], [1,15])
                    })
                self.cp2 = coverpoint(bit_t(4), bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp1X2 = cross([self.cp1, self.cp2])
                
        cg = my_covergroup()
        cg.init_model()

        cg.cp1.set_val(4)
        cg.cp2.set_val(4)
        cg.sample()
        cg.sample()
        
        cg.cp1.set_val(8)
        cg.cp2.set_val(8)
        cg.sample()
        cg.sample()
        
        cg.dump()                