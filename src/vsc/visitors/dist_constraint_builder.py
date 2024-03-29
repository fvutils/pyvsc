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
    
    def __init__(self, randstate):
        super().__init__()
        self.rng = randstate

    @staticmethod        
    def build(randstate, fm):
        builder = DistConstraintBuilder(randstate)
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
        for w in c.weights:
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
        # Sort in ascending order
        weight_list = []
        total_weight = 0
        for i,w in enumerate(c.weights):
            weight = int(w.weight.val())
            total_weight += weight
            if weight > 0:
                weight_list.append((weight, i))
        weight_list.sort(key=lambda w:w[0])

        scope.weight_list = weight_list
        scope.total_weight = total_weight

        # Call next_target_range for solvegroup_swizzler_range to use
        _ = scope.next_target_range(self.rng)

        self.override_constraint(scope)
        
        