'''
Created on Nov 7, 2020

@author: mballance
'''
from vsc.model.variable_bound_max_propagator import VariableBoundMaxPropagator

class VariableBoundBoundsMaxPropagator(VariableBoundMaxPropagator):
    """
    Propagator to enforce a max on a target bounds based on 
    the maximum value of another bounds model
    """
    
    def __init__(self,
                 target,
                 other,
                 offset=0):
        super().__init__(target)
        self.other = other
        self.offset = offset
        
    def max(self):
        return (self.other.domain.range_l[-1][1]+self.offset)
    