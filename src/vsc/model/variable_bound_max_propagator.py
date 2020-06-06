'''
Created on May 30, 2020

@author: ballance
'''
from vsc.model.variable_bound_propagator import VariableBoundPropagator
from vsc.model.expr_model import ExprModel

class VariableBoundMaxPropagator(VariableBoundPropagator):
    
    def __init__(self,
                 target : 'VariableBoundModel',
                 max_e : ExprModel):
        super().__init__(target)
        self.max_e = max_e
        
    def propagate(self):
        # Obtain the max value from the
        max_v = int(self.max_e.val())
  
        range_l = self.target.domain.range_l
        i=len(range_l)-1

        # Note: assume domain ranges are ordered
        # Find the first interval where the minimum is less than the max
        while i > 0:
            if range_l[i][0] <= max_v:
                break
            else:
                i -= 1
            
        must_propagate = False
        if i >= 0:
#            print("i: " + str(i) + " " + str(self.target.domain.range_l[i][0]))
            if range_l[i][1] > max_v:
                range_l[i][1] = max_v
                must_propagate = True
                
            if i < len(range_l)-1:
                # Need to trim off full range elements
                must_propagate = True
#                print("Removing domain element " + str(range_l[i+1]))
                self.target.domain.range_l = range_l[:i+1]
        else:
            print("ran off the end")
            
        if must_propagate:
            # Notify any propagators using the target as a source
            self.target.propagate()
