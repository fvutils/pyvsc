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
Created on Dec 23, 2019

@author: ballance
'''

import vsc
from vsc_test_case import VscTestCase


class TestRandomizeWith(VscTestCase):
    
    def test_smoke(self):

        @vsc.randobj
        class my_class(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(16)
                self.c = vsc.rand_bit_t(16)
                self.d = vsc.rand_bit_t(16)
#                 self.e = rand_bit_t(16)
#                 self.f = rand_bit_t(16)
#                 self.g = rand_bit_t(16)

#            @vsc.constraint
#            def abc_c(self):
#                self
                
            @vsc.constraint
            def my_a_c(self):
                self.a < 10
                with vsc.if_then(self.a == 2):
                    self.b < 1000
                with vsc.else_then():
                    self.b < 2000
                
        c = my_class()

        for i in range(1000):
#            c.randomize()
            with c.randomize_with() as it:
                it.a == (i%10)
            self.assertEquals(it.a, (i%10))
        
            print("i=" + str(i) + " c.a=" + hex(c.a) + " c.b=" + hex(c.b) + " c.c=" + hex(c.c) + " c.d=" + hex(c.d))
            

    def test_randomize_with_randselect(self):
                    
        @vsc.randobj
        class my_class:
            def __init__(self):
                self.value = vsc.rand_bit_t(32)
                self.randselect = self.get_val()
        
            def task(self, a, b):
                print("self.value: %d" % self.value)
                with vsc.raw_mode():
                    with vsc.randomize_with(self.value):
                        self.value in vsc.rangelist(a, b)
            
            def get_val(self):
                vsc.randselect([
                (1, lambda: self.task(0x12345678, 0x9abcdef0)),
                        (0, lambda: self.task(0x232456ab, 0x00000000))])
        
        
        obj = my_class()
        print("self.randselect", obj.value)



