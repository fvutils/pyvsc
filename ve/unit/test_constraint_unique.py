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
'''
Created on Jul 28, 2019

@author: ballance
'''

import unittest
import vsc
from enum import Enum, auto
from unittest.case import TestCase

from .vsc_test_case import VscTestCase


class TestConstraintUnique(VscTestCase):

    def test_simple(self):

        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(4)
                self.b = vsc.rand_bit_t(4)
                self.c = vsc.rand_bit_t(4)
                self.d = vsc.rand_bit_t(4)
                
            @vsc.constraint
            def ab_c(self):
                
                self.a != 0
                self.b != 0
                self.c != 0
                self.d != 0
                
                vsc.unique(self.a, self.b, self.c, self.d)

        v = my_s()
        v.randomize()
        
        print("a=" + str(v.a) + " b=" + str(v.b) + " c=" + str(v.c) + " d=" + str(v.d))

    def test_linked(self):

        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.v1_1 = vsc.rand_bit_t(4)
                self.v1_2 = vsc.rand_bit_t(4)
                self.v1_3 = vsc.rand_bit_t(4)
                self.v1_4 = vsc.rand_bit_t(4)
                self.v1_5 = vsc.rand_bit_t(4)
                self.v1_6 = vsc.rand_bit_t(4)
                self.v1_7 = vsc.rand_bit_t(4)
                self.v1_8 = vsc.rand_bit_t(4)
                self.v1_9 = vsc.rand_bit_t(4)
                self.v1_10 = vsc.rand_bit_t(4)
                self.v1_11 = vsc.rand_bit_t(4)
                self.v1_12 = vsc.rand_bit_t(4)
                self.v1_13 = vsc.rand_bit_t(4)
                self.v1_14 = vsc.rand_bit_t(4)
                self.v1_15 = vsc.rand_bit_t(4)
                self.v1_16 = vsc.rand_bit_t(4)
                self.v2_1 = vsc.rand_bit_t(4)
                self.v2_2 = vsc.rand_bit_t(4)
                self.v2_3 = vsc.rand_bit_t(4)
                self.v2_4 = vsc.rand_bit_t(4)
                self.v2_5 = vsc.rand_bit_t(4)
                self.v2_6 = vsc.rand_bit_t(4)
                self.v2_7 = vsc.rand_bit_t(4)
                self.v2_8 = vsc.rand_bit_t(4)
                self.v2_9 = vsc.rand_bit_t(4)
                self.v2_10 = vsc.rand_bit_t(4)
                self.v2_11 = vsc.rand_bit_t(4)
                self.v2_12 = vsc.rand_bit_t(4)
                self.v2_13 = vsc.rand_bit_t(4)
                self.v2_14 = vsc.rand_bit_t(4)
                self.v2_15 = vsc.rand_bit_t(4)
                self.v2_16 = vsc.rand_bit_t(4)                
                self.v3_1 = vsc.rand_bit_t(4)
                self.v3_2 = vsc.rand_bit_t(4)
                self.v3_3 = vsc.rand_bit_t(4)
                self.v3_4 = vsc.rand_bit_t(4)
                self.v3_5 = vsc.rand_bit_t(4)
                self.v3_6 = vsc.rand_bit_t(4)
                self.v3_7 = vsc.rand_bit_t(4)
                self.v3_8 = vsc.rand_bit_t(4)
                self.v3_9 = vsc.rand_bit_t(4)
                self.v3_10 = vsc.rand_bit_t(4)
                self.v3_11 = vsc.rand_bit_t(4)
                self.v3_12 = vsc.rand_bit_t(4)
                self.v3_13 = vsc.rand_bit_t(4)
                self.v3_14 = vsc.rand_bit_t(4)
                self.v3_15 = vsc.rand_bit_t(4)
                self.v3_16 = vsc.rand_bit_t(4)                
                self.v4_1 = vsc.rand_bit_t(4)
                self.v4_2 = vsc.rand_bit_t(4)
                self.v4_3 = vsc.rand_bit_t(4)
                self.v4_4 = vsc.rand_bit_t(4)
                self.v4_5 = vsc.rand_bit_t(4)
                self.v4_6 = vsc.rand_bit_t(4)
                self.v4_7 = vsc.rand_bit_t(4)
                self.v4_8 = vsc.rand_bit_t(4)
                self.v4_9 = vsc.rand_bit_t(4)
                self.v4_10 = vsc.rand_bit_t(4)
                self.v4_11 = vsc.rand_bit_t(4)
                self.v4_12 = vsc.rand_bit_t(4)
                self.v4_13 = vsc.rand_bit_t(4)
                self.v4_14 = vsc.rand_bit_t(4)
                self.v4_15 = vsc.rand_bit_t(4)
                self.v4_16 = vsc.rand_bit_t(4)                
                
            @vsc.constraint
            def ab_c(self):
                vsc.unique(
                    self.v1_1, self.v1_2, self.v1_3, self.v1_4,
                    self.v1_5, self.v1_6, self.v1_7, self.v1_8,
                    self.v1_9, self.v1_10, self.v1_11, self.v1_12,
                    self.v1_13, self.v1_14, self.v1_15, self.v1_16)
#                vsc.unique(self.v1_16, self.v2_1)
                vsc.unique(
                    self.v2_1, self.v2_2, self.v2_3, self.v2_4,
                    self.v2_5, self.v2_6, self.v2_7, self.v2_8,
                    self.v2_9, self.v2_10, self.v2_11, self.v2_12,
                    self.v2_13, self.v2_14, self.v2_15, self.v2_16)
#                vsc.unique(self.v2_16, self.v3_1)
                vsc.unique(
                    self.v3_1, self.v3_2, self.v3_3, self.v3_4,
                    self.v3_5, self.v3_6, self.v3_7, self.v3_8,
                    self.v3_9, self.v3_10, self.v3_11, self.v3_12,
                    self.v3_13, self.v3_14, self.v3_15, self.v3_16)
#                vsc.unique(self.v3_16, self.v4_1)
                vsc.unique(
                    self.v4_1, self.v4_2, self.v4_3, self.v4_4,
                    self.v4_5, self.v4_6, self.v4_7, self.v4_8,
                    self.v4_9, self.v4_10, self.v4_11, self.v4_12,
                    self.v4_13, self.v4_14, self.v4_15, self.v4_16)

        v = my_s()
        for i in range(10):
            v.randomize()
        
            print("v1_1=%d v1_2=%d v1_3=%d v1_4=%d" %
              (v.v1_1, v.v1_2, v.v1_3, v.v1_4))
            print("v2_1=%d v2_2=%d v2_3=%d v2_4=%d" %
              (v.v2_1, v.v2_2, v.v2_3, v.v2_4))
            print("v3_1=%d v3_2=%d v3_3=%d v3_4=%d" %
              (v.v3_1, v.v3_2, v.v3_3, v.v3_4))

    def test_unique_list(self):
        class my_e(Enum):
            num1= 0
            num2= auto()
            num3 = auto()
            num4 = auto()
            num5 = auto()
            num6 = auto()
            
        @vsc.randobj
        class my_cls(object):
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.enum_t(my_e), sz=3)  # self.a is a list of size 3
                self.b = vsc.rand_enum_t(my_e)
                self.c = vsc.rand_enum_t(my_e)
    
            @vsc.constraint
            def a_c(self):
                vsc.unique(self.a, self.b, self.c)

        my = my_cls()
        
        for i in range(10):
            my.randomize()
            total_l = []
            for av in my.a:
                total_l.append(av)
            total_l.append(my.b)
            total_l.append(my.c)
            
            print("a=%s b=%s c=%s" % (str(my.a), str(my.b), str(my.c)))
            for j in range(len(total_l)):
                for k in range(j+1, len(total_l)):
                    self.assertNotEqual(total_l[j], total_l[k])
            
                    
