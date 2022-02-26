
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

from vsc.types import rangelist
from vsc_test_case import VscTestCase


'''
Created on Jul 28, 2019

@author: ballance
'''

import unittest
from unittest.case import TestCase
import vsc

class TestIfElse(VscTestCase):

    def test_if_then(self):

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
                
                with vsc.if_then(self.a == 1):
                    self.b == 1

        v = my_s()
        v.randomize()

        v.a = 1
        v.a = 2
            
    def test_else_if(self):

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
                
                self.a in rangelist(1,5)
                
                with vsc.if_then(self.a == 1):
                    self.b in rangelist(0,10)
                with vsc.else_if(self.a == 2):
                    self.b in rangelist(11,20)
                with vsc.else_if(self.a == 3):
                    self.b in rangelist(21,30)
                with vsc.else_if(self.a == 4):
                    self.b in rangelist(31,40)
                with vsc.else_if(self.a == 5):
                    self.b in rangelist(41,50)

        v = my_s()
        for i in range(8):
            v.randomize()
            print("a=" + str(v.a) + " b=" + str(v.b))

    def test_else_if_2(self):

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
                with vsc.else_then():
                    self.b == 0

        v = my_s()
        for i in range(8):
            v.randomize()
            print("a=" + str(v.a) + " b=" + str(v.b))

    def test_else_if_3(self):

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
                with vsc.else_then:
                    self.b == 0

        v = my_s()
        for i in range(8):
            v.randomize()
            print("a=" + str(v.a) + " b=" + str(v.b))
                                
    def test_else_then(self):

        @vsc.randobj
        class my_s(object):
            
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
        
    def test_enum_if_else(self):
        import vsc
        from enum import IntEnum
        
        
        class CmdTypes(IntEnum):
            TYPE_A = 0
            TYPE_B = 1
        
        
        @vsc.randobj
        class Cmd():
            def __init__(self):
                self.cmd_type = vsc.rand_enum_t(CmdTypes)
                self.cmd_op = vsc.rand_bit_t(1)
        
            @vsc.constraint
            def op_type_combination_c(self):
                with vsc.if_then(self.cmd_type == CmdTypes.TYPE_B):  # This if_then is needed to hit the bug.
                   self.cmd_op == 1
        
        
        cmd = Cmd()
        cmd.randomize()    # This randomize() causes a TypeError in VSC.
        print(f"Cmd type:  {cmd.cmd_type}, Cmd op:  {cmd.cmd_op}")
        
        
