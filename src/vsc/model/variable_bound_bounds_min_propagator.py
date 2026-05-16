'''
Created on Nov 7, 2020

@author: mballance
'''
from vsc.model.variable_bound_min_propagator import VariableBoundMinPropagator

class VariableBoundBoundsMinPropagator(VariableBoundMinPropagator):
    
    def __init__(self,
                 target,
                 other,
                 offset=0):
        super().__init__(target)
        self.other = other
        self.offset = offset
        
        # Ensure we re-evaluate when the other bounds change
        other.add_propagator(self)
        
    def min(self):
        # Guard against empty domain
        if len(self.other.domain.range_l) == 0:
            # Return a very large value to force constraint failure
            return 2**63
        return (self.other.domain.range_l[0][0]+self.offset)
    