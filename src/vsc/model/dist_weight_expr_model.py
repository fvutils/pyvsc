'''
Created on Aug 9, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class DistWeightExprModel(ExprModel):

    def __init__(self,
                 rng_lhs : ExprModel,
                 rng_rhs : ExprModel,
                 weight : ExprModel,
                 is_per_value : bool = None):
        self.rng_lhs = rng_lhs
        self.rng_rhs = rng_rhs
        self.weight = weight
        # SystemVerilog dist distinguishes `:=` (weight applies to *each* value
        # in the range) from `:/` (weight *divided across* the range). pyvsc's
        # legacy front-end exposed only one form, whose effective behavior is
        # `:/` (the swizzler selects the range by weight, then picks uniformly
        # within it). The native dv-solve `add_dist` carries this as
        # `is_per_value`; record it here so the back-end can map it directly.
        # Default preserves legacy behavior: a single value is inherently
        # per-value (lo==hi), a range defaults to `:/` (per-range).
        if is_per_value is None:
            is_per_value = (rng_rhs is None)
        self.is_per_value = is_per_value

    def accept(self, v):
        v.visit_dist_weight(self)
