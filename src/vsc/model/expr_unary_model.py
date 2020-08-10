'''
Created on Apr 28, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel
from vsc.model.unary_expr_type import UnaryExprType
from pyboolector import Boolector

class ExprUnaryModel(ExprModel):
    
    def __init__(self, op, e):
        super().__init__()
        self.expr = e
        self.op = op
        
    def build(self, btor : Boolector):
        ret = None
        
        if self.op == UnaryExprType.Not:
            ret = btor.Not(self.expr.build(btor))
        
        return ret
        ExprModel.build(self, btor)
        
    def accept(self, v):
        v.visit_expr_unary(self)