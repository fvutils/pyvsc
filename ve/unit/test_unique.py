
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

class TestUnique(TestCase):

    def test_simple(self):
        
        @vsc.rand_obj
        class my_s():
            
            def __init__(self):
                self.a = vsc.rand_bit_t(3)
                self.b = vsc.rand_bit_t(3)
                self.c = vsc.rand_bit_t(3)
                self.d = vsc.rand_bit_t(3)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a != 0
                self.b != 0
                self.c != 0
                self.d != 0
                
                vsc.unique(self.a, self.b, self.c, self.d)

        v = my_s()
        vsc.randomize(v)
        
        print("a=" + str(v.a()) + " b=" + str(v.b()) + " c=" + str(v.c()) + " d=" + str(v.d()))
        
        