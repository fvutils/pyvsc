'''
Created on May 30, 2020

@author: ballance
'''
from vsc.model.variable_bound_propagator import VariableBoundPropagator
from vsc.model.expr_model import ExprModel

class VariableBoundMinPropagator(VariableBoundPropagator):
    
    def __init__(self,
                 target : 'VariableBoundModel',
                 min_e : ExprModel):
        super().__init__(target)
        self.min_e = min_e
        
    def propagate(self):
        # Obtain the max value from the
        min_v = int(self.min_e.val())
  
        range_l = self.target.domain.range_l
        i=len(range_l)-1

        # Note: assume domain ranges are ordered
        # Find the first interval where the minimum is less than the max
        while i < len(range_l)-1 and range_l[i][0] < min_v:
            i += 1

        must_propagate = False
        if i < len(range_l):
            if i > 0:
                # Need to trim off full range elements
                must_propagate = True
                self.target.domain.range_l = range_l[i:]

            if min_v > range_l[0][0]:
                range_l[0][0] = min_v
                must_propagate = True
        else:
            print("ran off the end")
            
        if must_propagate:
            # Notify any propagators using the target as a source
            self.target.propagate()
