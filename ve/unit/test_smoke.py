
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
Created on Jul 23, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase

import vsc


class TestSmoke(TestCase):
    
    def test_smoke(self):
        
        @vsc.rand_obj
        class my_sub():
            
            def __init__(self):
                self.a = vsc.rand_attr(vsc.bit_t(4))

        @vsc.rand_obj        
        class my_rand():
            
            def __init__(self):
                self.a = vsc.rand_attr(vsc.bit_t(4))
                self.b = vsc.rand_attr(my_sub())
                
            @vsc.constraint
            def my_c(self):
                print("my_c: " + str(self))
#                self.a < 10
                
        
        v1 = my_rand()
#        v1.my_c.constraint_mode(0)
        v2 = my_rand()
#        v2.my_c.constraint_mode(0)
        vsc.randomize(v1)
        vsc.randomize(v1)

        