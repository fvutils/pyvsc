'''
Created on May 31, 2020

@author: ballance
'''
from vsc.model.variable_bound_propagator import VariableBoundPropagator

class VariableBoundEqPropagator(VariableBoundPropagator):
    
    def __init__(self, target, eq_e, is_const):
        super().__init__(target)
        self.eq_e = eq_e
        self.is_const = is_const
        
    def propagate(self):
        should_propagate = False
        
        if self.is_const:
            # Domain of the 
            pass
        