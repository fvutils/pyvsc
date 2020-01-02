'''
Created on Jan 1, 2020

@author: ballance
'''
from vsc.model.model_visitor import ModelVisitor

class FieldBuilderVisitor(ModelVisitor):
    
    def __init__(self, btor):
        super().__init__()
        self.btor = btor
        
    @staticmethod
    def build(obj, btor):
        v = FieldBuilderVisitor(btor)
        obj.accept(v)
        
    def visit_scalar_field(self, f):
        # Build a Boolector representation for each field
        f.build(self.btor)
            