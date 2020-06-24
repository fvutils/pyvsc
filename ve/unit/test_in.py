# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
'''
Created on Jul 28, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase

import vsc
from vsc_test_case import VscTestCase


class TestIn(VscTestCase):
    
    def test_single(self):

        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
#                self.a in vsc.rangelist(self.b+1, [self.b+2,self.c], 8)
                self.a in vsc.rangelist(1, 2, 4, 8)
               

                self.c != 0
                self.d != 0
                
                self.c < self.d
                self.b in vsc.rangelist([self.c,self.d])
                
        v = my_s()
        for i in range(100):
            v.randomize()
            print("a=" + str(v.a) + " b=" + str(v.b) + " c=" + str(v.c) + " d=" + str(v.d))        
        

    def test_single_d(self):

        @vsc.randobj        
        class my_s():
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                
#                self.a in vsc.rangelist(self.b+1, [self.b+2,self.c], 8)
                self.a in vsc.rangelist(1, 2, 4, 8)
               

                self.c != 0
                self.d != 0
                
                self.c < self.d
                self.b in vsc.rangelist([self.c,self.d])
                
        v = my_s()
        for i in range(100):
            v.randomize()
            print("a=" + str(v.a) + " b=" + str(v.b) + " c=" + str(v.c) + " d=" + str(v.d))       

    def test_in_indep(self):

        class obj(object):
            def __init__(self):
                pass
            
        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = obj()
                self.l = [2,3,4,5,6,7,8]
                
            @vsc.constraint
            def ab_c(self):
                
#                self.a in vsc.rangelist(self.b+1, [self.b+2,self.c], 8)
                self.a in vsc.rangelist(1, 2, [4,8])
                print("in: " + str(self.c in self.l))
               
        v = my_s()
        
        print("Model:\n" + ModelPrettyPrinter.print(v.get_model()))
        for i in range(10):
            v.randomize()
            print(v.a, v.b)
            
