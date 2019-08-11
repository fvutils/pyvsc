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
        # Visit constraints
        for c in f.constraint_model_l:
            c.accept(self)
    
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
        
        
        