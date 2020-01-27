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
from vsc.constraints import constraint_t
from vsc.types import type_base
from vsc.model.scalar_field_model import ScalarFieldModel
from vsc.impl.ctor import push_constraint_scope, pop_constraint_scope
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model import expr_mode, _expr_mode, get_expr_mode


class CompositeFieldModel():
    
    def __init__(self, user_obj, parent, is_rand):
        self.user_obj = user_obj
        self.parent = parent
        self.field_l = []
        self.constraint_model_l = []
        
        # Iterate through the fields and constraints
        # First, assign IDs to each of the randomized fields
        with expr_mode():
            for f in dir(user_obj):
                if not f.startswith("__") and not f.startswith("_int"):
                    fo = getattr(user_obj, f)
                
                    if isinstance(fo, type_base):
                    
                        fo._int_field_info.name = f
                        fo._int_field_info.id = len(self.field_l)
                        if self.parent != None:
                            fo._int_field_info.parent = self.parent.user_obj._int_field_info
                        self.field_l.append(ScalarFieldModel(fo, self, 
                                (is_rand and fo._int_field_info.is_rand)))
                    elif hasattr(fo, "_int_field_info"):
                        # This is a composite field
                        # TODO: assign ID
                        fo._int_field_info.name = f
                        fo._int_field_info.id = len(self.field_l)
                        if self.parent != None:
                            fo._int_field_info.parent = self.parent.t._int_field_info
                        self.field_l.append(CompositeFieldModel(fo, self, 
                                (is_rand and fo._int_field_info.is_rand)))
                    
                # Now, elaborate the constraints
            for f in dir(user_obj):
                if not f.startswith("__") and not f.startswith("_int"):
                    fo = getattr(user_obj, f)
                    if isinstance(fo, constraint_t):
                        push_constraint_scope(ConstraintBlockModel(f))
                        try:
                            fo.c(user_obj)
                        except Exception as e:
                            print("Exception while processing constraint: " + str(e))
                            raise e
                        self.constraint_model_l.append(pop_constraint_scope())
                    
                    
    def build(self, builder):
        # First, build the fields
        for f in self.field_l:
            f.build(builder)

        # Next, build out the constraints
        for c in self.constraint_model_l:
            c.build(builder)

#        for f in self.field_l:
#            if isinstance(f, CompositeFieldModel):
#                f.build
        
    def get_constraints(self, constraint_l):
        for f in self.field_l:
            f.get_constraints(constraint_l)
            
        for c in self.constraint_model_l:
            constraint_l.append(c)
            
    def get_fields(self, field_l):
        for f in self.field_l:
            if isinstance(f, CompositeFieldModel):
                f.get_fields(field_l)
            else:
                field_l.append(f)

    def pre_randomize(self):
        # Call the user's methods
        if hasattr(self.user_obj, "pre_randomize"):
            self.user_obj.pre_randomize()
            
        for f in self.field_l:
            f.pre_randomize()
    
    def post_randomize(self):
        for f in self.field_l:
            f.post_randomize()

    def accept(self, visitor):
        visitor.visit_composite_field(self)
            