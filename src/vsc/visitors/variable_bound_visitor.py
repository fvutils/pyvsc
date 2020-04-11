

# Created on Apr 4, 2020
#
# @author: ballance

from typing import Dict, List

from vsc.model.field_model import FieldModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel


class VariableBoundVisitor(ModelVisitor):
    """Establishes bounds for each variable based on constraints"""
    
    class VarInfo(object):
        
        def __init__(self, v):
            self.v = v
            self.val_set = None
            self.min = None
            self.max = None
    
    def __init__(self):
        super().__init__()
        self.field_info_m : Dict[FieldModel, VariableBoundVisitor.VarInfo] = {}
        self.phase = 0
        self.bound_m : Dict[FieldModel, 'VarInfo']
        self.changes = -1
        
    def process(self, variables, constraints) -> Dict[FieldModel, 'VarInfo']:
        self.bound_m : Dict[FieldModel, 'VarInfo'] = {}
        
        while self.changes > 0:
            self.changes = 0
            
            for v in variables:
                v.accept(self)
                
            for c in constraints:
                c.accept(self)
                
    def visit_expr_in(self, e : ExprInModel):
        self.bound_info_ret = None
        if isinstance(e.lhs, ExprFieldRefModel):
            f = e.lhs.fm
            info = VariableBoundVisitor.VarInfo(f)
            # TODO: different 
            info.val_set = e.rhs
            self.bound_info_ret = {f : info}
        else:
            print("Warning: expr-in on expression")
            e.accept(self)
                
    def visit_scalar_field(self, f:FieldScalarModel):
        # Fill in basic bound info
        if not f in self.bound_m.keys():
            info = VariableBoundVisitor.VarInfo(f)
            if f.is_signed:
                info.min = -(1 << (f.width-1))
                info.max = ((1 << (f.width-1))-1)
            else:
                info.min = 0
                info.max = ((1 << f.width)-1)
            
            self.bound_m[f] = info
            self.changes += 1
        
        
        
        

        