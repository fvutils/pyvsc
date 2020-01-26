'''
Created on Jan 25, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprRangelistModel(ExprModel):
    
    def __init__(self):
        super().__init__()
        self.rl = []
        
    def add_range(self, r):
        self.rl.append(r)
        
    def accept(self, v):
        v.visit_expr_rangelist(self)
        
    def __str__(self):
        ret = "["
        for i,ri in enumerate(self.rl):
            ret += str(ri)
            if i+1 < len(self.rl):
                ret += ","
        ret += "]"
        return ret