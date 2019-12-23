
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
                super().__init__(lambda a=bit_t(4) : 0)
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })
                
                self.finalize()
                
        cg = my_covergroup()
        
        cg.sample(5)
        cg.sample(4)
        cg.sample(4)
        
        cg.dump()
        
    def test_ref_covergroup(self):
        
        class my_covergroup(covergroup):
            
            def __init__(self, a, b):
                super().__init__()
                
                self.cp1 = coverpoint(a, cp_t=bit_t(8), bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp2 = coverpoint(b, cp_t=bit_t(8), bins={
                    "b" : bin_array([], [1,15])
                    })
                
                self.finalize()

        a = 1;
        b = 2;
        
        cg = my_covergroup(lambda:a, lambda:b)
        
        cg.sample()
        a = 2
        cg.sample()
        a = 3
        cg.sample()
        
        cg.dump()

    def test_emb_covergroup(self):
        
        class my_item_c(Base):
            
            class my_covergroup(covergroup):
                def __init__(self, it):
                    super().__init__()
                
                    self.cp1 = coverpoint(it.a, bins={
                        "a" : bin_array([], [1,15])
                    })
                    self.finalize()
            
            def __init__(self):
                self.a = rand_bit_t(8)
                self.cg = my_item_c.my_covergroup(self)

                self.a <= 1
                self.cg.sample()
                self.a <= 2
                self.cg.sample()
                self.a <= 3
                self.cg.sample()
                
        c = my_item_c()
        c.cg.dump()
                
    def test_class_covergroup(self):
       
        @rand_obj
        class my_rand():
            
            def __init__(self):
                self.a = rand_bit_t(4)
                self.b = rand_bit_t(4)
        
        class my_covergroup(covergroup):
            
            def __init__(self):
                super().__init__(lambda cls=my_rand() : 0)
                self.cp1 = coverpoint(self.cls.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.finalize()
                
        cg = my_covergroup()
        
        cls = my_rand()
        cls.a <= 4

        cg.sample(cls)
        
        cg.dump()        
        
    def test_simple_cross(self):
       
        class my_covergroup(covergroup):
            
            def __init__(self):
                super().__init__(lambda 
                        a=bit_t(4),
                        b=bit_t(4) : 0
                    )
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                self.cp2 = coverpoint(self.b, bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp1X2 = cross([self.cp1, self.cp2])

                # Finalize the model
                self.finalize()

        cg = my_covergroup()
        
        for i in range(100000):
            cg.sample(4, 4)
            cg.sample(4, 4)
         
            cg.sample(8, 8)
            cg.sample(8, 8)
        
        cg.dump()                