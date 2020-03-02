
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
Created on Jul 29, 2019

@author: ballance
'''
from unittest.case import TestCase
import vsc

class TestRandomization(TestCase):
                        
    def test_simple(self):

        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(2)
                self.d = vsc.rand_bit_t(1)
                self.e = vsc.rand_bit_t(16)
                self.f = vsc.rand_bit_t(8)
                self.g = vsc.rand_bit_t(2)
                self.h = vsc.rand_bit_t(1)
                self.i = vsc.rand_bit_t(16)
                self.j = vsc.rand_bit_t(8)
                self.k = vsc.rand_bit_t(2)
                self.l = vsc.rand_bit_t(1)
                
            @vsc.constraint
            def ab_c(self):
               
                with vsc.if_then(self.a < self.b):
                    self.c < self.d
                with vsc.else_then():
                    self.c == self.d
#                self.c != self.d
                pass

        v = my_s()
        
        for i in range(1000):
            v.randomize()
            
            print("a=" + str(v.a) + " b=" + str(v.b) + " c=" + str(v.c) + " d=" + str(v.d) + " e=" + str(v.e) + " f=" + str(v.f))
        
