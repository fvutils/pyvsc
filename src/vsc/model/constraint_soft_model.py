

# Created on Mar 18, 2020
#
# @author: ballance

from vsc.model.constraint_model import ConstraintModel
from vsc.model.expr_model import ExprModel

class ConstraintSoftModel(ConstraintModel):
    """Soft constraint expression"""
    
    def __init__(self, e : ExprModel):
        super().__init__()
        self.expr = e

    def build(self, btor):
        return self.expr.build(btor)
        
    def accept(self, v):
        v.visit_constraint_soft(self)
        
    def __str__(self):
        return "Soft: " + str(self.expr)

    