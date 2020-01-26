'''
Created on Jan 25, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprRangeModel(ExprModel):
    
    def __init__(self, lhs, rhs):
        super().__init__()
        self.lhs = lhs
        self.rhs = rhs
        
    def accept(self, v):
        v.visit_expr_range(self)
        
    def __str__(self):
        return "[" + str(self.lhs) + ":" + str(self.rhs) + "]"
