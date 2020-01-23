'''
Created on Jan 1, 2020

@author: ballance
'''
from vsc.model.constraint_scope_model import ConstraintScopeModel

class ConstraintBlockModel(ConstraintScopeModel):
    """Information about a top-level constraint block described by the user"""
    
    def __init__(self, name):
        super().__init__()
        self.name = name
        
    def accept(self, v):
        v.visit_constraint_block(self)
        