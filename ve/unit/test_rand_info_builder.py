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
# KIND, either express or implied.  See the License fjor the
# specific language governing permissions and limitations
# under the License.
'''
Created on Jan 22, 2020

@author: ballance
'''

import vsc
from vsc1.model.rand_info_builder import RandInfoBuilder
from vsc_test_case import VscTestCase


class TestRandInfoBuilder(VscTestCase):
    
    def test_no_refs(self):
       
        @vsc.randobj 
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)
                
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 0)
        self.assertEqual(len(info.unconstrained_l), 2)
        
    def test_single_var_ref(self):
       
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < 5
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 1)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 1)
        
    def test_multi_indep_var_ref(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < 5
                self.b ==  5
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 2)
        self.assertEqual(len(info.randset_l[0].fields()), 1)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.randset_l[1].fields()), 1)
        self.assertEqual(len(info.randset_l[1].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)
        
    def test_multi_dep_var_ref(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 2)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)

    def test_two_randsets(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                self.c < self.d
                
        my_cls_i = my_cls()
       
        model = my_cls_i.get_model()
        model.set_used_rand(True) 
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 2)
        self.assertEqual(len(info.randset_l[0].fields()), 2)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.randset_l[1].fields()), 2)
        self.assertEqual(len(info.randset_l[1].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)        

    def test_connected_top_level(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                self.b < self.c
                self.c < self.d
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 3)
        self.assertEqual(len(info.unconstrained_l), 0)        

    def test_connected_ite_cond(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                with vsc.if_then (self.b < self.c):
                    self.c < self.d
                
        my_cls_i = my_cls()
        
        model = my_cls_i.get_model()
        model.set_used_rand(True)
        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.unconstrained_l), 0)

    def test_connected_ite_cross_block(self):

        @vsc.randobj        
        class my_cls(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                    
            @vsc.constraint
            def b_c(self):
                with vsc.if_then (self.b < self.c):
                    self.c < self.d
                
        my_cls_i = my_cls()

        model = my_cls_i.get_model()
        model.set_used_rand(True)        
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.unconstrained_l), 0)        
        
