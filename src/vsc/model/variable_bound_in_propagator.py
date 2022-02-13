'''
Created on May 30, 2020

@author: ballance
'''
from vsc.model.variable_bound_propagator import VariableBoundPropagator
from vsc.model.variable_bound_model import VariableBoundModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter

class VariableBoundInPropagator(VariableBoundPropagator):
    
    DEBUG_EN = False
    
    def __init__(self,
                 target : VariableBoundModel,
                 in_e : ExprInModel):
        super().__init__(target)
        self.in_e = in_e
        
    def propagate(self):
        should_propagate = False
        
        # Intersect the 'in' rangelist and the domain
        # Note: assume both ranges are sorted, non-overlapping, and non-adjacent
        in_i = 0
        dom_i = 0

        # This should really be taken care of elsewhere...        
        in_r_l_t = list(map(lambda e:[int(e.lhs.val()),int(e.rhs.val())] if isinstance(e, ExprRangeModel) 
                          else [int(e.val()),int(e.val())], self.in_e.rl))
        in_r_l_t.sort(key=lambda e:e[0])
        in_r_l = []
#        in_r_l = in_r_l_t
        
        for i in range(0,len(in_r_l_t)):
            if len(in_r_l) > 0 and in_r_l[-1][1]+1 >= in_r_l_t[i][0]:
                in_r_l[-1][1] = in_r_l_t[i][1]
            else:
                in_r_l.append(in_r_l_t[i])
        
        if VariableBoundInPropagator.DEBUG_EN:
            print("--> propagate: " + str(in_r_l) + " " + self.target.domain.toString())
        
        result_l = []
        while in_i < len(in_r_l) and dom_i < len(self.target.domain.range_l):
            if (int(in_r_l[in_i][0]) > int(self.target.domain.range_l[dom_i][0])):
                r_left = int(in_r_l[in_i][0])
            else:
                r_left = int(self.target.domain.range_l[dom_i][0])
                
            if (int(in_r_l[in_i][1]) < int(self.target.domain.range_l[dom_i][1])):
                r_right = int(in_r_l[in_i][1])
            else:
                r_right = int(self.target.domain.range_l[dom_i][1])
                
            if (r_left <= r_right):
                result_l.append([r_left, r_right])

            if int(in_r_l[in_i][1]) < int(self.target.domain.range_l[dom_i][1]):
                in_i += 1
            else:
                dom_i += 1
                
        if len(self.target.domain.range_l) != len(result_l):
            should_propagate = True
        else:
            for i in range(len(result_l)):
                if self.target.domain.range_l[i][0] != result_l[i][0]:
                    should_propagate = True
                    break
                elif self.target.domain.range_l[i][1] != result_l[i][1]:
                    should_propagate = True
                    break
                
        self.target.domain.range_l = result_l
            
        if should_propagate:
            self.target.propagate()
            
        if VariableBoundInPropagator.DEBUG_EN:
            print("<-- propagate: " + str(in_r_l) + " " + self.target.domain.toString())
