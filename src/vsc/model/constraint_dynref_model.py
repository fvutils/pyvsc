'''
Created on Mar 26, 2020

@author: ballance
'''
from pyboolector import BoolectorNode

from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_model import ConstraintModel


class ConstraintDynRefModel(ConstraintModel):
    """Constraint that is a reference to a dynamic-constraint block"""
    
    def __init__(self, c : ConstraintBlockModel):
        super().__init__()
        self.c = c
        
    def build(self, btor)->BoolectorNode:
        print("ConstraintDynRefModel::build")
        return self.c.build(btor)
        
    def accept(self, v):
        v.visit_constraint_dynref(self)