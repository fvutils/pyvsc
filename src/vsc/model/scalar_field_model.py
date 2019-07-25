
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
        self.is_rand = is_rand
        self.parent = parent
        sort = btor.BitVecSort(f.width)
        self.var = btor.Var(sort)
        
#        self.v = btor.

    def get_constraints(self, constraint_l):
        if not self.is_rand:
            print("TODO: need to add constraint")
        pass

    def pre_randomize(self):
        pass
    
    def post_randomize(self):
        print("post-randomize: " + str(self.var.assignment))
            