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

from vsc.model.composite_field_model import CompositeFieldModel
from vsc.model.scalar_field_model import ScalarFieldModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_cond_model import ExprCondModel
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_bin_enum_model import CoverpointBinEnumModel
from vsc.model.coverpoint_bin_model import CoverpointBinModel



'''
Created on Aug 10, 2019

@author: ballance
'''

class ModelVisitor(object):
    
    def __init__(self):
        pass
    
    def visit_rand_obj(self, r):
        self.visit_composite_field(r)
        
    def visit_composite_field(self, f : CompositeFieldModel):
        # Visit fields
        for fi in f.field_l:
            fi.accept(self)
            
        # Visit constraints
        for c in f.constraint_model_l:
            c.accept(self)

    def visit_scalar_field(self, f : ScalarFieldModel):
        pass
    
    def visit_constraint_stmt_enter(self, c : ConstraintModel):
        """Called for all types of constraint statements"""
        pass
    
    def visit_constraint_stmt_leave(self, c : ConstraintModel):
        """Called for all types of constraint statements"""
        pass
    
    def visit_constraint_block(self, c : ConstraintBlockModel):
        self.visit_constraint_scope(c)
        
    def visit_constraint_expr(self, c : ConstraintExprModel):
        self.visit_constraint_stmt_enter(c)
        c.e.accept(self)
        self.visit_constraint_stmt_leave(c)
        
    def visit_constraint_if_else(self, c : ConstraintIfElseModel):
        self.visit_constraint_stmt_enter(c)
        c.cond.accept(self)
        c.true_c.accept(self)
        if c.false_c != None:
            c.false_c.accept(self)
        self.visit_constraint_stmt_leave(c)
            
    def visit_constraint_implies(self, c : ConstraintImpliesModel):
        self.visit_constraint_stmt_enter(c)
        c.cond.accept(self)
        self.visit_constraint_scope(c)
        self.visit_constraint_stmt_leave(c)
        
    def visit_constraint_scope(self, c : ConstraintScopeModel):
        for cc in c.constraint_l:
            cc.accept(self)
            
    def visit_constraint_unique(self, c : ConstraintUniqueModel):
        self.visit_constraint_stmt_enter(c)
        for e in c.unique_l:
            e.accept(self)
        self.visit_constraint_stmt_leave(c)
            
    def visit_expr_bin(self, e : ExprBinModel):
        e.lhs.accept(self)
        e.rhs.accept(self)
        
    def visit_expr_cond(self, e : ExprCondModel):
        e.cond_e.accept(self)
        e.true_e.accept(self)
        e.false_e.accept(self)
    
    def visit_expr_fieldref(self, e):
        pass
    
    def visit_expr_indexed_fieldref(self, e):
        pass
    
    def visit_expr_range(self, r):
        r.lhs.accept(self)
        r.rhs.accept(self)
    
    def visit_expr_rangelist(self, r):
        for ri in r.rl:
            ri.accept(self)
    
    def visit_expr_in(self, e):
        e.lhs.accept(self)
        e.rhs.accept(self)
        
    def visit_expr_literal(self, e):
        pass
    
    def visit_expr_partselect(self, e):
        e.lhs.accept(self)
        if e.rhs is not None:
            e.rhs.accept(self)
        
    def visit_covergroup_registry(self, rgy):
        
        for cg in rgy.covergroup_l:
            cg.accept(self)

    def visit_covergroup(self, cg : CovergroupModel):
        
        for cp in cg.coverpoint_l:
            cp.accept(self)
            
        for cr in cg.cross_l:
            cr.accept(self)

        # Visit type instances            
        for i in cg.cg_inst_l:
            i.accept(self)
   
    def visit_coverpoint(self, cp : CoverpointModel):
        for b in cp.bin_model_l:
            b.accept(self)
    
    def visit_coverpoint_bin_array(self, bn : CoverpointBinArrayModel):
        pass
    
    def visit_coverpoint_bin_collection(self, bn : CoverpointBinCollectionModel):
        for sb in bn.bin_l:
            sb.accept(self)
            
    def visit_coverpoint_bin(self, bn : CoverpointBinModel):
        pass
            
    def visit_coverpoint_bin_enum(self, bn : CoverpointBinEnumModel):
        pass
    
    def visit_coverpoint_bin_collection(self, bn : CoverpointBinCollectionModel):
        for sb in bn.bin_l:
            sb.accept(self)
            
    def visit_coverpoint_bin(self, bn : CoverpointBinModel):
        pass
            
    def visit_coverpoint_bin_enum(self, bn : CoverpointBinEnumModel):
        pass
    
    
            
    
    def visit_coverpoint_cross(self, cp):
        pass
    
