'''
Created on Jan 1, 2020

@author: ballance
'''
from vsc.model.model_visitor import ModelVisitor

class ConstraintBuilderVisitor(ModelVisitor):
    
    def __init__(self, btor):
        super().__init__()
        self.btor = btor
        
    @staticmethod
    def build(obj, btor):
        v = ConstraintBuilderVisitor(btor)
        obj.accept(v)
        
    def visit_constraint_block(self, c):
        self.btor.Assert(c.build(self.btor))
        