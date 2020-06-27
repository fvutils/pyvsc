'''
Created on Jun 27, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprArraySumModel(ExprModel):
    
    def __init__(self, arr):
        super().__init__()
        self.arr = arr
        
    def get_sum_expr(self):
        print("get_sum_expr")
        return self.arr.get_sum_expr()
        
    def build(self, btor):
        return self.arr.build_sum_expr(btor)
    
    def is_signed(self):
        return self.arr.is_signed
    
    def width(self):
        ret = self.arr.width
        if ret < 32:
            ret = 32
        return ret
    
    def accept(self, v):
        v.visit_expr_array_sum(self)
    