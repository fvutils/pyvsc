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

import vsc
from .vsc_test_case import VscTestCase
from vsc1.model.coverpoint_model import CoverpointModel


class TestRandomization(VscTestCase):
    
    def test_single(self):
        
        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(16)
                
            @vsc.constraint
            def ab_c(self):
                self.a < self.b
                
        my_i = my_s()
        
        for i in range(100):
            my_i.randomize()
            print("a=" + str(my_i.a) + " (" + bin(my_i.a) + ") b=" + str(my_i.b))
            self.assertLess(my_i.a, my_i.b)
                        
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
            
        @vsc.covergroup 
        class my_s_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint16_t()
                    ))
                self.a_cp = vsc.coverpoint(self.a)

        v = my_s()
        v_cg = my_s_cg()
        
        v_cg_m = v_cg.get_model()
        cp_m : CoverpointModel = v_cg_m.coverpoint_l[0]

        for b in cp_m.bin_model_l[0].bin_l:
            print("b: " + str(b.target_val_low) + ".." + str(b.target_val_high))
            
        
        
#        for i in range(1000):
        for i in range(500):
            v.randomize()
            v_cg.sample(v.a)
            print("a=" + str(v.a) + " b=" + str(v.b) + " c=" + str(v.c) + " d=" + str(v.d) + " e=" + str(v.e) + " f=" + str(v.f))

#        self.assertGreaterEqual(v_cg.get_coverage(), 70)

        print("Coverage: %f" % (v_cg.get_coverage()))
        print("cp_m=" + str(cp_m))
        
        for bi in range(cp_m.get_n_bins()):
            print("Bin[%d]=%d" % (bi, cp_m.get_bin_hits(bi)))
        

        
