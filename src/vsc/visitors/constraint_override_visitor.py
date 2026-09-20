'''
Created on May 19, 2020

@author: ballance
'''
from typing import List

from vsc.model.constraint_inline_scope_model import ConstraintInlineScopeModel
from vsc.model.constraint_override_model import ConstraintOverrideModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.visitors.constraint_copy_builder import ConstraintCopyBuilder


# Monotonic count of ConstraintOverrideModels installed into a model tree.
# `Randomizer.do_randomize` runs an O(n) rollback walk at the end of every
# randomize(); by snapshotting this counter at the top of the call and comparing
# at the bottom, it can tell whether *this* call installed anything and skip a
# walk that provably has nothing to find (Stage 1 / S1.4-C2 --
# doc/notes/vdc_stage1_impl_plan.md).
#
# Only two places install overrides -- ArrayConstraintBuilder (`foreach`
# expansion) and DistConstraintBuilder -- and both run on the plan-cache *cold*
# path only, so a warm randomize() installs nothing and the walk finds nothing.
# Measured: 0 installs and 0 rollback hits per warm solve on every benchmark
# workload, including the array ones.
#
# A per-call delta rather than an outstanding-balance: builders also override
# constraints inside *inline* constraint objects, which the rollback walk (which
# only traverses the field-model tree) never reaches, so a balance counter drifts
# up without bound and would disable the skip permanently. An override that the
# walk can reach is always fully rolled back by the same call's walk --
# ConstraintOverrideModel.depth starts at 1, so one visit restores it -- which is
# what makes "did this call install anything?" the exact condition.
#
# Nesting is safe: `cyclic.py` can call do_randomize recursively, and because the
# counter is monotonic an inner call's installs also make the outer call run its
# walk. Conservative in the right direction.
installs = 0


def note_installed():
    global installs
    installs += 1


class ConstraintOverrideVisitor(ConstraintCopyBuilder):
    
    def __init__(self):
        super().__init__()
        self.scope_s : List[ConstraintScopeModel] = []
        self.scope_i = 0
        
    def visit_constraint_scope(self, c:ConstraintScopeModel):
        self.scope_s.append(c)
        for i,cc in enumerate(c.constraint_l):
            self.scope_i = i
            cc.accept(self)
        self.scope_s.pop()
            
    def visit_constraint_inline_scope(self, c:ConstraintInlineScopeModel):
        self.scope_s.append(c)
        for i,cc in enumerate(c.constraint_l):
            self.scope_i = i
            cc.accept(self)
        self.scope_s.pop()
            
    def override_constraint(self, new_constraint):
        """Replace the active constraint with a replacement"""
        self.scope_s[-1].constraint_l[self.scope_i] = ConstraintOverrideModel(
            self.scope_s[-1].constraint_l[self.scope_i],
            new_constraint)
        note_installed()
        

        