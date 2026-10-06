'''
Created on May 18, 2021

@author: mballance
'''
from typing import List, Tuple
from vsc.model.constraint_inline_scope_model import ConstraintInlineScopeModel
from vsc.model.constraint_dist_model import ConstraintDistModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.rand_state import RandState

class ConstraintDistScopeModel(ConstraintInlineScopeModel):
    """Holds implementation data about dist constraint"""
    
    def __init__(self, dist_c, constraints=None):
        super().__init__(constraints)
        
        self.dist_c : ConstraintDistModel = dist_c
        
        self.dist_soft_c : ConstraintSoftModel = None

        # List of (weight, index) tuples
        self.weight_list : List[Tuple[int, int]] = []
        self.total_weight = 0

        # Rand fields referenced by weight expressions. Weights that
        # depend on these can only be evaluated once the fields are solved
        self.weight_field_l = []

        # Indicates the current-target range. This is used to
        # by solvegroup_swizzler_range.
        self.target_range = 0

    def update_weights(self):
        """(Re)compute the weight list from the current weight-expression values"""
        self.weight_list = []
        self.total_weight = 0
        for i,w in enumerate(self.dist_c.weights):
            weight = int(w.weight.val())
            if weight > 0:
                self.total_weight += weight
                self.weight_list.append((weight, i))
        self.weight_list.sort(key=lambda w:w[0])

    def next_target_range(self, randstate : RandState) -> int:
        """Select the next target range from the weight list"""

        if self.total_weight <= 0:
            # All weights are zero. The hard constraints exclude
            # every value, so there is nothing to target
            return None

        seed_v = randstate.rng.randint(1, self.total_weight)

        # Find the first range
        i = 0
        while i < len(self.weight_list):
            seed_v -= self.weight_list[i][0]

            if seed_v <= 0:
                break

            i += 1

        if i >= len(self.weight_list):
            i = len(self.weight_list)-1

        self.target_range = self.weight_list[i][1]

        return self.target_range
        
    def set_dist_soft_c(self, c : ConstraintSoftModel):
        self.addConstraint(c)
        self.dist_soft_c = c
        
    def accept(self, v):
        v.visit_constraint_dist_scope(self)