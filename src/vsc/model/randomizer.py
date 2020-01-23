'''
Created on Jan 21, 2020

@author: ballance
'''
from vsc.model.field_model import FieldModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.model_visitor import ModelVisitor

class Randomizer():
    
    class VarCollectVisitor(ModelVisitor):
        def __init__(self, field_s):
            super().__init__()
            self.field_s = field_s
        
        def visit_scalar_field(self, f):
            self.field_l.add(f)
            
    class FieldSet():
        def __init__(self):
            self.constraint_l = []
            self.var_s = set()
            
        def add_var(self, var):
            self.var_s.add(var)
            
        def add_constraint(self, c):
            self.constraint_l.append(c)
            
    class ConstraintSetBuilder(ModelVisitor):
        def __init__(self, field_s):
            super().__init__()
            self.field_s = field_s
            self.field_set_m = {}
            self.field_set_l = []
            
        def visit_constraint_expr(self, c):
            
    
    
    def randomize(self, 
        field_model_l : [FieldModel], 
        constraint_l : [ConstraintModel]):
        """Randomize a top-level set of variables and additional constraints"""
        
        # Collect all variables from the list provided$
        all_field_s = set()
        var_collector_visitor = Randomizer.VarCollectVisitor(all_field_s)
        for fm in field_model_l:
            fm.accept(var_collector_visitor)
        
        
        # Process constraints to identify variable/constraint sets
        