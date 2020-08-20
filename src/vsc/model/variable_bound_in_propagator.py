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
    
    def __init__(self,
                 target : VariableBoundModel,
                 in_e : ExprInModel):
        super().__init__(target)
        self.in_e = in_e
        
    def propagate(self):
#        print("--> propagate")

        should_propagate = False
        
        # Intersect the 'in' rangelist and the domain
        # Note: assume both ranges are sorted, non-overlapping, and non-adjacent
        in_i = 0
        dom_i = 0

        # This should really be taken care of elsewhere...        
        in_r_l = list(map(lambda e:[int(e.lhs.val()),int(e.rhs.val())] if isinstance(e, ExprRangeModel) 
                          else [int(e.val()),int(e.val())], self.in_e.rl))
        in_r_l.sort(key=lambda e:e[0])
        
        prev_in_r_v = None
        dom_r = None
        while in_i < len(in_r_l) and dom_i < len(self.target.domain.range_l):
            in_r_v = in_r_l[in_i]
            dom_r = self.target.domain.range_l[dom_i]
            
#             print("in_i=" + str(in_i) + " dom_i=" + str(dom_i))
#             print("  in_r_v=" + str(int(in_r_v[0])) + ".." + str(int(in_r_v[1])))
#             print("  dom_r=" + str(dom_r[0]) + ".." + str(dom_r[1]))
            
            # Check to see if the range starts above the domain element
            if int(in_r_v[0]) > dom_r[1]:
                # Check whether the last element preserved
                if prev_in_r_v is not None and int(prev_in_r_v[1]) >= dom_r[0] and int(prev_in_r_v[1]) <= dom_r[1]:
                    # The previous inside element was inside this domain element
                    # We need to adjust the reachable domain
#                    print("Reduce domain max " + str(dom_r[1]) + " -> " + str(int(prev_in_r_v[1])))
                    dom_r[1] = int(prev_in_r_v[1])
                    should_propagate = (prev_in_r_v[1] < dom_r[1])
                    dom_i += 1
                else:
                    # The previous element wasn't inside either. Discard
#                    print("Discarding domain element")
                    self.target.domain.range_l.pop(dom_i)
                    should_propagate = True
            elif int(in_r_v[0]) > dom_r[0]:
                if prev_in_r_v is not None and int(prev_in_r_v[1]) >= dom_r[0]:
                    # Must partition the domain
#                    print("Creating a new domain partition")
                    should_propagate = True
                    self.target.domain.range_l.insert(
                        dom_i, 
                        [dom_r[0], int(prev_in_r_v[1])])
                    dom_i += 1
                        
#                print("Narrowing domain min " + str(dom_r[0]) + " -> " + str(in_r_v[0]))
                dom_r[0] = int(in_r_v[0])
                should_propagate = True
                
                if int(in_r_v[1]) < dom_r[1]:
#                    print("Advancing inside")
                    in_i += 1
                    prev_in_r_v = in_r_v
                else:
#                    print("Advancing domain")
                    dom_i += 1
            else:
#                print("Advancing both domain and inside")
                prev_in_r_v = in_r_v
                in_i += 1
                dom_i += 1

        if dom_r[1] > int(in_r_v[1]):
#            print("Reducing final domain: " + str(dom_r[0]) + ".." + str(dom_r[1]) + " " + str(int(in_r_v[0])) + ".." + str(int(in_r_v[1])))
            dom_r[1] = int(in_r_v[1])
            should_propagate = True
        
            
        if should_propagate:
            self.target.propagate()
            
#        print("<-- propagate")
