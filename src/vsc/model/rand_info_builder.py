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

# Created on Jan 22, 2020
#
# @author: ballance


from builtins import set
from typing import Set, Dict, List

from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.rand_if import RandIF
from _random import Random

from vsc.model.constraint_model import ConstraintModel
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.field_model import FieldModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.rand_info import RandInfo
from vsc.model.rand_set import RandSet
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.field_array_model import FieldArrayModel


class RandInfoBuilder(ModelVisitor,RandIF):
    
    def __init__(self, rng):
        # TODO: need access to the random state
        super().__init__()
        self._pass = 0
        self._field_s = set()
        self._active_constraint = None
        self._active_randset = None
        self._randset_s : Set[RandSet] = set()
        self._randset_field_m : Dict[FieldModel,RandSet] = {} # map<field,randset>
        self._constraint_s : List[ConstraintModel] = []
        self._used_rand = True
        self._in_generator = False
        self.active_cp = None
        self._rng = rng
        
    @staticmethod
    def build(
            field_model_l : [FieldModel],
            constraint_l : [ConstraintModel],
            rng=None) ->RandInfo:
        if rng is None:
            rng = Random()
            
        builder = RandInfoBuilder(rng)

        # First, collect all the fields
        builder._pass = 0
        for fm in field_model_l:
            fm.accept(builder)
            
        # Now, build the randset
        builder._pass = 1
        builder._used_rand = True
        # Visit the field objects passed in, as well
        # as their constraints
        for fm in field_model_l:
            fm.accept(builder)

        # Visit standalone constraints passed to the function
        for c in constraint_l:
            c.accept(builder)
            
#         for rs in builder._randset_s:
#             print("RS: " + str(rs))
#             for c in rs.constraint_s:
#                 print("RS Constraint: " + str(c))
            
        return RandInfo(list(builder._randset_s), list(builder._field_s))
    
    def randint(self, low:int, high:int)->int:
        return self._rng.randint(low,high)
    
    def sample(self, s, k):
        return self._rng.sample(s, k)
    
    def visit_constraint_block(self, c):
        if not c.enabled:
            # Ignore constraint blocks that aren't enabled
            return
        
        # Null out the randset on entry to a constraint block
        if self._used_rand:
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
        c_blk = self._constraint_s[0]
        self._constraint_s.pop()
        if self._pass == 1 and len(self._constraint_s) == 1:
            if self._active_randset is not None:
                self._active_randset.add_constraint(c)
            else:
#                print("TODO: handle no-reference constraint: " + str(c_blk.name))
                pass
        super().visit_constraint_stmt_leave(c)
        
    def visit_constraint_dynref(self, c):
        # Treat a dynamic constraint as an inline expansion
        # of the constraints in the referenced block
        for c_stmt in c.c.constraint_l:
            c_stmt.accept(self)
    
    def visit_constraint_expr(self, c):
        super().visit_constraint_expr(c)
        
    def visit_constraint_soft(self, c:ConstraintSoftModel):
        super().visit_constraint_soft(c)
        
    def visit_expr_array_subscript(self, s : ExprArraySubscriptModel):
        fm = s.getFieldModel()
        if self._pass == 1:
            # During pass 1, build out randsets based on constraint
            # relationships

            # If the field is already referenced by an existing randset
            # that is not this one, we need to merge the sets
            if fm in self._randset_field_m.keys():
                # There's an existing randset that holds this field
                ex_randset = self._randset_field_m[fm]
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
                self._active_randset.add_field(fm)
                self._randset_field_m[fm] = self._active_randset
                
            if fm in self._field_s:
                self._field_s.remove(fm)
        
    def visit_expr_fieldref(self, e):
        
        if self._pass == 1:
            # During pass 1, build out randsets based on constraint
            # relationships

            # If the field is already referenced by an existing randset
            # that is not this one, we need to merge the sets
            if isinstance(e.fm, FieldArrayModel):
                for f in e.fm.field_l:
                    self.process_fieldref(f)
            else:
                self.process_fieldref(e.fm)
 

        super().visit_expr_fieldref(e)
        
    def process_fieldref(self, fm):
        if fm in self._randset_field_m.keys():
            # There's an existing randset that holds this field
            ex_randset = self._randset_field_m[fm]
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
            self._active_randset.add_field(fm)
            self._randset_field_m[fm] = self._active_randset
            
        if fm in self._field_s:
            self._field_s.remove(fm)        
        
        
    def visit_composite_field(self, f):
        old_used_rand = self._used_rand
        self._used_rand = f.is_used_rand
        super().visit_composite_field(f)
        self._used_rand = old_used_rand
        
    def visit_scalar_field(self, f):
        if self._pass == 0:
            self._field_s.add(f)
            
    def visit_enum_field(self, f):
        if self._pass == 0:
            self._field_s.add(f)
            
    def visit_covergroup(self, cg:CovergroupModel):
        
        if not self._in_generator or self._pass != 1:
            return

        # TODO: in the case of multiple covergroups, need to have 
        # made a higher-level decision about which covergroup to target
        # TODO: determine which coverpoints we're going to enable
        # First try: just select one
        unhit_cp = []
        for cp in cg.coverpoint_l:
            if cp.get_coverage() != 100:
                unhit_cp.append(cp)
        for cp in cg.cross_l:
            if cp.get_coverage() != 100:
                unhit_cp.append(cp)
                
        if len(unhit_cp) > 0:
            # Only process the target coverpoint
            target_cp = self.randint(0, len(unhit_cp)-1)
            bin_idx = unhit_cp[target_cp].select_unhit_bin(self)
            bin_expr = unhit_cp[target_cp].get_bin_expr(bin_idx)
            c = ConstraintSoftModel(bin_expr)
            cc = ConstraintBlockModel("coverage", [c])
            cc.accept(self)
                
    def visit_generator(self, g):
        self._in_generator = True
        super().visit_generator(g)
        self._in_generator = False

