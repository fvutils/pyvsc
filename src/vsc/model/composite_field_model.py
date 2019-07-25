
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
from vsc.constraints import constraint_t
from vsc.types import type_base
from vsc.model.scalar_field_model import ScalarFieldModel


class CompositeFieldModel():
    
    def __init__(self, t, parent, is_rand, btor):
        self.t = t
        self.parent = parent
        self.field_l = []
        
      # Iterate through the fields and constraints
        # First, assign IDs to each of the randomized fields
        for f in dir(t):
            if not f.startswith("__") and not f.startswith("_int"):
                fo = getattr(t, f)
                
                if isinstance(fo, type_base):
                    
                    print("ATTR field: " + f)
                    fo._int_field_info.name = f
                    fo._int_field_info.id = len(self.field_l)
                    if self.parent != None:
                        fo._int_field_info.parent = self.parent.t._int_field_info
                    print("Scalar field: " + f)
                    self.field_l.append(ScalarFieldModel(fo, self, 
                                (is_rand and fo._int_field_info.is_rand), btor))
                elif hasattr(fo, "_int_rand_info"):
                    # This is a composite field
                    # TODO: assign ID
                    print("Composite field: " + f)
                    fo._int_field_info.name = f
                    fo._int_field_info.id = len(self.field_l)
                    if self.parent != None:
                        fo._int_field_info.parent = self.parent.t._int_field_info
                    self.field_l.append(CompositeFieldModel(fo, self, 
                                (is_rand and fo._int_field_info.is_rand), btor))
                    
        # Now, elaborate the constraints
        for f in dir(t):
            if not f.startswith("__") and not f.startswith("_int"):
                fo = getattr(t, f)
                print("f: " + f + " " + str(fo))
                if isinstance(fo, constraint_t):
                    fo.c(t)
                    print("Found a constraint")                
        
    def get_constraints(self, constraint_l):
        for f in self.field_l:
            f.get_constraints(constraint_l)

    def pre_randomize(self):
        # Call the user's methods
        if hasattr(self.t, "pre_randomize"):
            self.t.pre_randomize()
            
        for f in self.field_l:
            f.pre_randomize()
    
    def post_randomize(self):
        for f in self.field_l:
            f.post_randomize()
            