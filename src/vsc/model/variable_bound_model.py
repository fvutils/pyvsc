'''
Created on May 30, 2020

@author: ballance
'''
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.rangelist_model import RangelistModel
from vsc.model.variable_bound_propagator import VariableBoundPropagator
from typing import List

class VariableBoundModel(object):
    
    def __init__(self, var : FieldScalarModel):
        self.var = var
        self.domain : RangelistModel = RangelistModel()
        self.propagators : List[VariableBoundPropagator] = []
        
        # Fill in base domain information
        if var.is_signed:
            self.domain.add_range(-(1 << var.width-1), (1 << var.width-1)-1)
        else:
            self.domain.add_range(0, (1 << var.width)-1)
            
    def add_propagator(self, p):
        self.propagators.append(p)
            
    def propagate(self):
        for p in self.propagators:
            p.propagate()
            
    