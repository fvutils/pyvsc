
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
Created on Jan 22, 2020

@author: ballance
'''
from vsc.model.model_visitor import ModelVisitor
from vsc.model.field_model import FieldModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.rand_info import RandInfo
from builtins import set
from vsc.model.rand_set import RandSet

class RandInfoBuilder(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self._pass = 0
        self._field_s = set()
        self._active_constraint = None
        self._active_randset = None
        self._randset_s = set()
        self._randset_field_m = {} # map<field,randset>
        self._constraint_s = []
        
    @staticmethod
    def build(
            field_model_l : [FieldModel],
            constraint_l : [ConstraintModel]) ->RandInfo:
        builder = RandInfoBuilder()

        # First, collect all the fields
        builder._pass = 0
        for fm in field_model_l:
            fm.accept(builder)
            
        # Now, build the randset
        builder._pass = 1
        # Visit the field objects passed in, as well
        # as their constraints
        for fm in field_model_l:
            fm.accept(builder)
        # Visit standalone constraints passed to the function
        for c in constraint_l:
            c.accept(builder)
            
        return RandInfo(list(builder._randset_s), list(builder._field_s))
    
    def visit_constraint_block(self, c):
        # Null out the randset on entry to a constraint block
        self._active_randset = None
        self._constraint_s.append(c)
        super().visit_constraint_block(c)
        self._constraint_s.clear()
        
    def visit_constraint_stmt_enter(self, c):
        if self._pass == 1 and len(self._constraint_s) == 1:
            self._active_randset = None
        self._constraint_s.append(c)
        super().visit_constraint_stmt_enter(c)
        
    def visit_constraint_stmt_leave(self, c):
        self._constraint_s.pop()
        if self._pass == 1 and len(self._constraint_s) == 1:
            if self._active_randset is not None:
                self._active_randset.add_constraint(c)
            else:
                print("TODO: handle no-reference constraint: " + str(c))
        super().visit_constraint_stmt_leave(c)
    
    def visit_constraint_expr(self, c):
        super().visit_constraint_expr(c)
        
    def visit_expr_fieldref(self, e):
        if self._pass == 1:
            # During pass 1, build out randsets based on constraint
            # relationships

            # If the field is already referenced by an existing randset
            # that is not this one, we need to merge the sets
            if e.fm in self._randset_field_m.keys():
                # There's an existing randset that holds this field
                ex_randset = self._randset_field_m[e.fm]
                if self._active_randset is None:
                    self._active_randset = ex_randset
                elif ex_randset is not self._active_randset:
                    for f in self._active_randset.fields():
                        # Relink to the new consolidated randset
                        self._randset_field_m[f] = ex_randset
                        ex_randset.add_field(f)
                    # TODO: this might be later
                    for c in self._active_randset.constraints():
                        ex_randset.add_constraint(c)

                    # Remove the previous randset
                    self._randset_s.remove(self._active_randset)                    
                    self._active_randset = ex_randset
            else:
                # No existing randset holds this field
                if self._active_randset is None:
                    self._active_randset = RandSet()
                    self._randset_s.add(self._active_randset)
                    
                # Need to register this field/randset mapping
                self._active_randset.add_field(e.fm)
                self._randset_field_m[e.fm] = self._active_randset
                
            if e.fm in self._field_s:
                self._field_s.remove(e.fm)

        super().visit_expr_fieldref(e)

    def visit_scalar_field(self, f):
        if self._pass == 0:
            self._field_s.add(f)
    