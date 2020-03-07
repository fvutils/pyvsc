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
from vsc.model.field_model import FieldModel

'''
Created on Jul 24, 2019

@author: ballance
'''

class ScalarFieldModel(FieldModel):
    
    def __init__(self, 
        name,
        width,
        is_signed,
        is_rand,
        rand_if): 
        super().__init__(name)
        self.name = name
        self.width = width
        self.is_signed = is_signed
        self.is_declared_rand = is_rand
        self.is_used_rand = is_rand
        self.rand_if = rand_if
        self.var = None
        self.val = 0
        
    def set_used_rand(self, is_rand, level):
        self.is_used_rand = (is_rand and (self.is_declared_rand or level==0))
        
    def dispose(self):
        self.var = None
        
    def accept(self, v):
        v.visit_scalar_field(self)

    def build(self, btor):
        if self.is_used_rand:
            sort = btor.BitVecSort(self.width)
            self.var = btor.Var(sort)
        else:
            print("Non-rand var")
            self.var = btor.Const(self.val, self.width)
        return self.var
    
    def get_full_name(self):
        ret = self.name
        p = self.parent
        
        while p is not None:
            ret = p.name + "." + ret
            p = p.parent

        return ret
        
        
    def __str__(self):
        return "ScalarFieldModel(" + self.get_full_name() + ")"

    def get_constraints(self, constraint_l):
        pass

    def pre_randomize(self):
        if self.rand_if is not None:
            self.rand_if.do_pre_randomize()
    
    def set_val(self, val):
        self.val = val
        
    def get_val(self):
        return self.val
    
    def post_randomize(self):
        if self.var is not None:
            val = 0
            for b in self.var.assignment:
                val <<= 1
                if b == '1':
                    val |= 1
            self.set_val(val)
            
        if self.rand_if is not None:
            self.rand_if.do_post_randomize()
