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

from unittest import TestCase

import vsc
from .vsc_test_case import VscTestCase


class TestPartSelect(VscTestCase):

    def test_simple(self):

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
                self.c != 0
                self.d != 0
                
                vsc.unique(self.a, self.b, self.c, self.d)

        v = my_s()
        v.randomize()
        
        print("a=" + hex(v.a) + " b=" + hex(v.b) + " c=" + hex(v.c) + " d=" + hex(v.d))

        try:
            with v.randomize_with() as it:
                self.c == 0
        except:
            print("expected failure")
 

