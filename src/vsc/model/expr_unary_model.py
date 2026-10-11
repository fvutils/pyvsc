'''
Created on Apr 28, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel
from vsc.model.unary_expr_type import UnaryExprType

class ExprUnaryModel(ExprModel):
    
    def __init__(self, op, e):
        super().__init__()
        self.expr = e
        self.op = op
        
    def build(self, btor : "Boolector", ctx_width=-1):
        ret = None
        
        e_w = self.expr.width()
        if e_w > ctx_width:
            ctx_width = e_w
        
        
        if self.op == UnaryExprType.Not:
            # SV: the operand takes the context width before it is inverted,
            # so ~a of a u8 'a' compared at 32 bits has its upper bits set.
            from vsc.model.expr_bin_model import ExprBinModel
            e = ExprBinModel.extend(self.expr.build(btor, ctx_width),
                                    ctx_width, self.expr.is_signed(), btor)
            ret = btor.Not(e)
        
        return ret
    
    def width(self):
        # Currently-supported unary expressions have the
        # same width as the base expression
        return self.expr.width()

    def is_signed(self):
        # A unary op (bitwise ~/Not) preserves the operand's signedness.
        return self.expr.is_signed()

    def accept(self, v):
        v.visit_expr_unary(self)