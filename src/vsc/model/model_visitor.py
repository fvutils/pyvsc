
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
Created on Aug 10, 2019

@author: ballance
'''

class ModelVisitor():
    
    def __init__(self):
        pass
    
    def visit_rand_obj(self, r):
        self.visit_composite_field(r)
            
    def visit_composite_field(self, f):
        # Visit fields
        for fi in f.field_l:
            fi.accept(self)
            
        # Visit constraints
        for c in f.constraint_model_l:
            c.accept(self)

    def visit_scalar_field(self, f):
        pass
    
    def visit_constraint_block(self, c):
        self.visit_constraint_scope(c)
        
    def visit_constraint_expr(self, c):
        c.e.accept(self)
        
    def visit_constraint_if_else(self, c):
        c.cond.accept(self)
        c.true_c.accept(self)
        if c.false_c != None:
            c.false_c.accept(self)
            
    def visit_constraint_implies(self, c):
        c.cond.accept(self)
        self.visit_constraint_scope(c)
        
    def visit_constraint_scope(self, c):
        for cc in c.constraint_l:
            cc.accept(self)
            
    def visit_constraint_unique(self, c):
        for e in c.unique_l:
            e.accept(self)
            
    def visit_expr_bin(self, e):
        e.lhs.accept(self)
        e.rhs.accept(self)
        
    def visit_expr_cond(self, e):
        e.cond_e.accept(self)
        e.true_e.accept(self)
        e.false_e.accept(self)
    
    def visit_expr_fieldref(self, e):
        pass
    
    def visit_expr_in(self, e):
        e.lhs.accept(self)
        e.rhs.accept(self)
        
    def visit_expr_literal(self, e):
        pass
    
    def visit_expr_partselect(self, e):
        e.lhs.accept(self)
        e.rhs.accept(self)
        
    def visit_covergroup_registry(self, rgy):
        
        for cg in rgy.covergroup_l:
            cg.accept(self)

    def visit_covergroup(self, cg):
        
        for cp in cg.coverpoint_l:
            cp.accept(self)
            
        for cr in cg.cross_l:
            cr.accept(self)
   
    def visit_coverpoint(self, cp):
        pass
    
    def visit_coverpoint_cross(self, cp):
        pass
    
