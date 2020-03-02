
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

from unittest.case import TestCase
from vsc.types import rand_uint16_t
from vsc.attrs import rand_attr, attr
import vsc


class TestCompoundObj(TestCase):
    
    def test_rand_compound(self):

        @vsc.randobj        
        class C1(object):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()

        @vsc.randobj                
        class C2(object):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = rand_attr(C1())
                
        c2 = C2()
        
        for i in range(10):
            c2.randomize()
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b))

    def disabled_test_rand_compound_nonrand(self):

        @vsc.randobj        
        class C1(object):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()
                
        @vsc.randobj
        class C2(object):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = attr(C1())
                
                @vsc.constraint
                def c1_c2_c(self):
                    self.c1.a == self.c2.a
                
        c2 = C2()
        
        for i in range(10):
            c2.c2.a = i
            print("c2.c2.a=" + str(c2.c2.a))
            c2.randomize()  
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b) + " c2.a=" + str(c2.c2.a))    
            self.assertEqual(c2.c1.a, i)
    