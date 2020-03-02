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
Created on Jul 24, 2019

@author: ballance
'''

class ScalarFieldModel():
    
    def __init__(self, 
        name,
        width,
        is_signed,
        is_rand,
        rand_if): 
        self.name = name
        self.width = width
        self.is_signed = is_signed
        self.is_rand = is_rand
        self.rand_if = rand_if
        self.parent = None
        self.var = None
        self.val = 0
        
    def dispose(self):
        self.var = None
        
    def accept(self, v):
        v.visit_scalar_field(self)

    def build(self, btor):
        sort = btor.BitVecSort(self.width)
        self.var = btor.Var(sort)
        
    def get_node(self):
        """Returns the node that represents the solver field"""
        return self.var
    
    def __str__(self):
        return "ScalarFieldModel(" + self.name() + ")"

    def get_constraints(self, constraint_l):
        if not self.is_rand:
            print("TODO: need to add constraint")
        pass

    def pre_randomize(self):
        if self.rand_if is not None:
            self.rand_if.pre_randomize()
    
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
            self.rand_if.post_randomize()
