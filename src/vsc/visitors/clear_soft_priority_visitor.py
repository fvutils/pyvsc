'''
Created on May 23, 2021

@author: mballance
'''
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.model_visitor import ModelVisitor


class ClearSoftPriorityVisitor(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self.visited = set()
        
    def clear(self, e):
        self.visited.clear()
        e.accept(self)
        
    def visit_constraint_soft(self, c:ConstraintSoftModel):
        c.priority = 0

    def visit_composite_field(self, f: FieldCompositeModel):
        if f not in self.visited:
            self.visited.add(f)
            super().visit_composite_field(f)
        