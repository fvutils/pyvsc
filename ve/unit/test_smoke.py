
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
Created on Jul 23, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase

import vsc


class TestSmoke(TestCase):
    
    def test_smoke(self):

        @vsc.randobj        
        class my_sub(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(4)
                self.b = vsc.rand_bit_t(4)
                self.c = vsc.rand_bit_t(4)
                self.d = vsc.rand_bit_t(4)

        @vsc.randobj
        class my_rand(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(4)
                self.b = vsc.rand_attr(my_sub())
                self.c = vsc.rand_attr(my_sub())
                self.d = vsc.rand_attr(my_sub())
                self.e = vsc.rand_attr(my_sub())
                
            @vsc.constraint
            def my_c(self):
                print("my_c: " + str(self))
                self.a == 10
                self.b.a == 2
                self.b.b != 0
                self.b.c > 2
                self.b.d <= 2
                self.b.d != 0
                
        
        v1 = my_rand()
        for i in range(10):
            v1.randomize()
            print("a=" + str(v1.a) + " b.a=" + str(v1.b.a) + " b.d=" + str(v1.b.d))
#        vsc.randomize(v1)
        
#        print("v1.a=" + str(int(v1.a)))
