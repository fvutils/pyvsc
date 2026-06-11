'''
Created on Aug 9, 2020

@author: ballance
'''
from vsc.model.constraint_inline_scope_model import ConstraintInlineScopeModel
from vsc.model.model_visitor import ModelVisitor
from vsc.visitors.constraint_override_visitor import ConstraintOverrideVisitor
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_unary_model import ExprUnaryModel
from vsc.model.unary_expr_type import UnaryExprType
from vsc.model.constraint_soft_model import ConstraintSoftModel
import random
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc.model.constraint_dist_scope_model import ConstraintDistScopeModel


class DistConstraintBuilder(ConstraintOverrideVisitor):

    def __init__(self, randstate, native=False):
        super().__init__()
        self.rng = randstate
        # native=True => the active back-end consumes `dist` natively (its own
        # weighted picker handles weighting and zero-weight exclusion). We then
        # emit only the hard `inside` membership (which also serves as the
        # back-end's completeness "twin") and the weight bookkeeping the
        # Boolector swizzler needs on fallback — but NOT the zero-weight
        # exclusion implications. Those are redundant with the native picker and,
        # crucially, the native compiler rejects them (they would force a
        # spurious fallback). See dv_solve_phaseB_dist_plan.md §B-4.
        self.native = native

    @staticmethod
    def build(randstate, fm, native=False):
        builder = DistConstraintBuilder(randstate, native=native)
        fm.accept(builder)

    def visit_constraint_dist(self, c):
        # We replace the dist constraint with an equivalent
        # set of hard and soft constraints
        scope = ConstraintDistScopeModel(c)

        ranges = ExprRangelistModel()
        for w in c.weights:
            if w.rng_rhs is not None:
                # two-value range
                ranges.add_range(ExprRangeModel(w.rng_lhs, w.rng_rhs))
            else:
                # single value
                ranges.add_range(w.rng_lhs)

        # First, create an 'in' constraint to restrict
        # values to the appropriate value set
        in_c = ConstraintExprModel(
            ExprInModel(c.lhs, ranges))
        scope.addConstraint(in_c)

        # Now, we need to add exclusion constraints for any
        # zero weights
        # (!w) -> (lhs != [val])
        # (!w) -> (lns not in [rng])
        # Skipped on the native path: the back-end's own picker excludes
        # zero-weight entries, and these implications don't compile there.
        for w in ([] if self.native else c.weights):
            if w.rng_rhs is not None:
                scope.addConstraint(ConstraintImpliesModel(
                    ExprBinModel(
                        w.weight,
                        BinExprType.Eq,
                        ExprLiteralModel(0, False, 8)),
                    [
                        ConstraintExprModel(
                            ExprUnaryModel(
                                UnaryExprType.Not,
                                    ExprBinModel(
                                        ExprBinModel(
                                            c.lhs,
                                            BinExprType.Ge,
                                            w.rng_lhs),
                                    BinExprType.And,
                                        ExprBinModel(
                                            c.lhs,
                                            BinExprType.Le,
                                            w.rng_rhs))))
                    ]))
            else:
                scope.addConstraint(ConstraintImpliesModel(
                    ExprBinModel(
                        w.weight,
                        BinExprType.Eq,
                        ExprLiteralModel(0, False, 8)),
                    [
                        ExprUnaryModel(
                            UnaryExprType.Not,
                            ExprBinModel(
                                c.lhs,
                                BinExprType.Eq,
                                w.rng_lhs))
                    ]))

        # Form a list of non-zero weighted tuples of weight/range
        # Sort in ascending order.
        #
        # The swizzler picks a range proportional to its weight, then a uniform
        # value within it. That realizes `:/` (weight applies to the range as a
        # whole). For `:=` (is_per_value) the weight applies to *each* value, so
        # the range's selection weight is scaled by its value count — wider
        # ranges then draw proportionally more, matching native add_dist.
        weight_list = []
        total_weight = 0
        for i,w in enumerate(c.weights):
            weight = int(w.weight.val())
            if getattr(w, "is_per_value", False) and w.rng_rhs is not None:
                width = int(w.rng_rhs.val()) - int(w.rng_lhs.val()) + 1
                if width > 1:
                    weight *= width
            total_weight += weight
            if weight > 0:
                weight_list.append((weight, i))
        weight_list.sort(key=lambda w:w[0])

        scope.weight_list = weight_list
        scope.total_weight = total_weight

        # Prime an initial target range for solvegroup_swizzler_range. This
        # consumes randstate, so it must be skipped on the native path: a native
        # back-end ignores the swizzler entirely, and the consumption would
        # otherwise make a plan-cache *hit* (which skips this expansion) diverge
        # from a *miss* for the same seed — breaking per-seed reproducibility.
        # The partsel swizzler (what Boolector uses) re-picks per solve, so the
        # priming call is redundant for the fallback path too.
        if not self.native:
            _ = scope.next_target_range(self.rng)

        self.override_constraint(scope)
        
        