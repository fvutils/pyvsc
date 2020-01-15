'''
Created on Jan 2, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprCondModel(ExprModel):
    
    def __init__(self, cond_e, true_e, false_e):
        super().__init__()
        self.cond_e = cond_e
        self.true_e = true_e
        self.false_e = false_e
        
    def build(self, btor):
        cond_n = self.cond_e.build(btor)
        true_n = self.true_e.build(btor)
        false_n = self.false_e.build(btor)
        
        return btor.Cond(cond_n, true_n, false_n)
    
    def is_signed(self):
        return self.true_e.signed or self.false_e.signed
    
    def width(self):
        return 0
        
    def accept(self, visitor):
        visitor.visit_expr_cond(self)
