
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
Created on Jul 28, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase
import vsc

class TestIfElse(TestCase):

    def test_if_then(self):
        
        class my_s(vsc.Base):
            
            def __init__(self):
                super().__init__()
                
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a == 4
                
                with vsc.if_then(self.a == 1):
                    self.b == 1

        v = my_s()
        v.randomize()
        
        print("a=" + str(int(v.a)) + " b=" + str(int(v.b)))
            
    def test_else_if(self):
        
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a == 5
                
                with vsc.if_then(self.a == 1):
                    self.b == 1
                with vsc.else_if(self.a == 2):
                    self.b == 2
                with vsc.else_if(self.a == 3):
                    self.b == 4
                with vsc.else_if(self.a == 4):
                    self.b == 8
                with vsc.else_if(self.a == 5):
                    self.b == 16

        v = my_s()
        vsc.randomize(v)
        
    def test_else_then(self):
        
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a == 1
                
                with vsc.if_then(self.a == 1):
                    self.b == 1
                with vsc.else_then():
                    self.b == 2

        v = my_s()
        vsc.randomize(v)        
        