
#   Copyright 2019 Matthew Ballance
#   All Rights Reserved Worldwide
#
#   Licensed under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in
#   compliance with the License.  You may obtain a copy of
#   the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in
#   writing, software distributed under the License is
#   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, either express or implied.  See
#   the License for the specific language governing
#   permissions and limitations under the License.

'''
Created on Jul 24, 2019

@author: ballance
'''

class ScalarFieldModel():
    
    def __init__(self, f, parent, is_rand, btor):
        self.f = f
        # Connect the user facade to the model
        self.f._int_field_info.model = self
        self.is_rand = is_rand
        self.parent = parent
        sort = btor.BitVecSort(self.f.width)
        self.var = btor.Var(sort)

    def build(self, builder):
        pass
        
    def get_node(self):
        return self.var
    
    def width(self):
        return self.f.width
    
    def name(self):
        return self.f._int_field_info.name

    def get_constraints(self, constraint_l):
        if not self.is_rand:
            print("TODO: need to add constraint")
        pass

    def pre_randomize(self):
        # TODO: need to sample non-rand field
        pass
    
    def post_randomize(self):
        val = 0
        for b in self.var.assignment:
            val <<= 1
            if b == '1':
                val |= 1
        self.f.val = val
            