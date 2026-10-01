'''
Created on Jun 2, 2020

@author: ballance
'''
from vsc.model.variable_bound_model import VariableBoundModel
from vsc.model.field_scalar_model import FieldScalarModel

class VariableBoundScalarModel(VariableBoundModel):
    
    def __init__(self, var : FieldScalarModel):
        super().__init__(var)
        
        # Fill in base domain information
        if var.is_signed:
            w_lo, w_hi = -(1 << var.width-1), (1 << var.width-1)-1
        else:
            w_lo, w_hi = 0, (1 << var.width)-1

        # A declared domain (``vdc.rand(domain=...)``) *intersects* the width
        # range -- it never widens the field, and it is the only place a domain
        # enters the solve, since it deliberately produces no constraint. An
        # empty intersection leaves an empty domain, which isEmpty()/the normal
        # UNSAT path reports rather than silently drawing a value.
        dd = getattr(var, "declared_domain", None)
        if dd is None:
            self.domain.add_range(w_lo, w_hi)
        else:
            from vsc.dc.domain import intersect
            for lo, hi in intersect(dd.ranges, [[w_lo, w_hi]]):
                self.domain.add_range(lo, hi)
