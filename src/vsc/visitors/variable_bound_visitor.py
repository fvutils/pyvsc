

# Created on Apr 4, 2020
#
# @author: ballance

from typing import Dict, List

from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_inline_scope_model import ConstraintInlineScopeModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.enum_field_model import EnumFieldModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.field_model import FieldModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.variable_bound_enum_model import VariableBoundEnumModel
from vsc.model.variable_bound_eq_propagator import VariableBoundEqPropagator
from vsc.model.variable_bound_in_propagator import VariableBoundInPropagator
from vsc.model.variable_bound_max_propagator import VariableBoundMaxPropagator
from vsc.model.variable_bound_min_propagator import VariableBoundMinPropagator
from vsc.model.variable_bound_model import VariableBoundModel
from vsc.model.variable_bound_scalar_model import VariableBoundScalarModel
from vsc.visitors.is_const_expr_visitor import IsConstExprVisitor
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter


class VariableBoundVisitor(ModelVisitor):
    """Establishes bounds for each variable based on constraints"""
    
    def __init__(self):
        super().__init__()
        self.field_info_m : Dict[FieldModel, VariableBoundVisitor.VarInfo] = {}
        # Collect variables during phase1
        # Compute bounds during phase2
        self.phase = 0
        self.bound_m : Dict[FieldModel, VariableBoundModel] = {}
        self._propagator = None
        self._expr = None
        self.depth = 0
        self.process_subscript = True
        
    def process(self, 
                variables,
                constraints,
                process_subscript=True) -> Dict[FieldModel, 'VarInfo']:
        self.bound_m : Dict[FieldModel, 'VarInfo'] = {}
        self.process_subscript = process_subscript
        
        # Tracks how deep we are in expressions, so we know
        # how to process expressions
        self.depth = 0
        
        self.phase = 0
        for v in variables:
            v.accept(self)
            
            
        self.phase = 1
        for v in variables:
            v.accept(self)
        for c in constraints:
            c.accept(self)
            
        # Update data calcuated from domain ranges
        for f,b in self.bound_m.items():
            b.update()

    def visit_constraint_if_else(self, c:ConstraintIfElseModel):
        if self.phase == 1:
            self.depth += 1
            super().visit_constraint_if_else(c)
            self.depth -= 1
    
    def visit_constraint_implies(self, c:ConstraintImpliesModel):
        if self.phase == 1:
            self.depth += 1
            super().visit_constraint_implies(c)
            self.depth -= 1
            
    def visit_constraint_inline_scope(self, c:ConstraintInlineScopeModel):
        for cc in c.constraint_l:
            cc.accept(self)
    
    def visit_constraint_foreach(self, f:ConstraintForeachModel):
        # Don't go into an unexpanded foreach block. This 
        # construct is a meta-constraint that will be expanded
        pass
    
    def visit_constraint_unique(self, c:ConstraintUniqueModel):
        # Don't go into an unexpanded unique block. This 
        # construct is a meta-constraint that will be expanded
        pass
    
    def visit_expr_bin(self, e:ExprBinModel):
        # TODO: We'll need to deal with expressions that involve variables
        # An alias is the simplest relationship. A == B means that there is
        # a single bound for both variables, and all relationships on A and B
        # contribute to this single bound

        # Don't attempt to deal with subscripts when we're
        # establishing array domains.        
        if not self.process_subscript and (
            isinstance(e.lhs, ExprArraySubscriptModel) or 
            isinstance(e.rhs, ExprArraySubscriptModel)):
            return
      
        if self.phase == 1:
            # Traverse to pick up variable references
            super().visit_expr_bin(e)
            
            if isinstance(e.lhs, ExprArraySubscriptModel):
                fm = e.lhs.subscript()
            elif isinstance(e.lhs, ExprFieldRefModel):
                fm = e.lhs.fm
            else:
                fm = None

            if self.depth > 0:
                # Ignore processing if we're deep in an expression
                pass            
            elif fm is not None and not isinstance(e.rhs, ExprFieldRefModel):
                bounds = self.bound_m[fm]
                if e.op == BinExprType.Lt:
                    # TODO: 
                    # The max bound is 
                    self._propagator = VariableBoundMaxPropagator(
                        bounds,
                        ExprBinModel(
                            e.rhs,
                            BinExprType.Sub,
                            ExprLiteralModel(1, False, 4)))
                    
                    bounds.add_propagator(self._propagator)
                    
                    # Apply propagator
                    self._propagator.propagate()
                    
                    self._propagator = None
                elif e.op == BinExprType.Le:
                    # TODO: 
                    # The max bound is 
                    self._propagator = VariableBoundMaxPropagator(
                        bounds,
                        e.rhs)
                    
                    bounds.add_propagator(self._propagator)
                    
                    # Apply propagator
                    self._propagator.propagate()
                    
                    self._propagator = None
                elif e.op == BinExprType.Gt:
                    # TODO: 
                    # The minimum bound is 1+ RHS
                    self._propagator = VariableBoundMinPropagator(
                        bounds,
                        ExprBinModel(
                            e.rhs,
                            BinExprType.Add,
                            ExprLiteralModel(1, False, 4)))
                    
                    bounds.add_propagator(self._propagator)
                    
                    # Apply propagator
                    self._propagator.propagate()
                    
                    self._propagator = None
                elif e.op == BinExprType.Ge:
                    # TODO: 
                    # The minimum bound is 1+ RHS
                    self._propagator = VariableBoundMinPropagator(
                        bounds,
                        e.rhs)
                    
                    bounds.add_propagator(self._propagator)
                    
                    # Apply propagator
                    self._propagator.propagate()
                    
                    self._propagator = None
                elif e.op == BinExprType.Eq:
                    is_const_v = IsConstExprVisitor()
                    is_const = is_const_v.is_const(e.rhs)
                    
                    if is_const:
                        self._propagator = VariableBoundEqPropagator(
                            bounds,
                            e.rhs,
                            True)
                    elif isinstance(e.rhs, ExprFieldRefModel):
                        # TODO: lhs is an alias
#                        self._propagator = VariableBoundEqPropagator(
#                            bounds,
#                            self.bound_m[e.rhs.fm],
#                            True)
                        pass

                    if self._propagator is not None:                    
                        bounds.add_propagator(self._propagator)
                        self._propagator.propagate()
#                     
#                     self._propagator = None
                    
            elif isinstance(e.rhs, ExprFieldRefModel):
                # TODO: Need to do similar calculation for RHS
                pass
                

    def visit_expr_in(self, e : ExprInModel):
        if self.phase == 1:
            if self.depth > 0:
                pass
            elif isinstance(e.lhs, ExprFieldRefModel):
                is_const_v = IsConstExprVisitor()
                bounds = self.bound_m[e.lhs.fm]

                # Confirm that all expressions are constants
                is_const = True
                for r in e.rhs.rl:
                    if isinstance(r, list):
                        is_const &= is_const_v.is_const(r[0])
                        is_const &= is_const_v.is_const(r[1])
                    else:
                        is_const &= is_const_v.is_const(r)
                    
                    if not is_const:
                        break

                if is_const:
                    self._propagator = VariableBoundInPropagator(bounds, e.rhs)
                    bounds.add_propagator(self._propagator)
                    self._propagator.propagate()
                    
                    self._propagator = None
                    
    def visit_expr_array_subscript(self, s):
        # This only exists until we flatten out array references
        pass
                
    def visit_expr_fieldref(self, e):
        if self.phase == 1:
            # TODO: We're collecting fields that are part of 
            # a limiting expression. Need to add the propagator
            # to these variables as well
            if e.fm in self.bound_m.keys():
                bounds = self.bound_m[e.fm]
                bounds.constrained = True
#                bounds.add_propagator(self._propagator)
            else:
                raise Exception("Field " + e.fm.name + " not in map")
            
    def visit_scalar_field(self, f:FieldScalarModel):
        if self.phase == 0:
            # Fill in basic bound info
            if not f in self.bound_m.keys():
                bounds = VariableBoundScalarModel(f)
                self.bound_m[f] = bounds
                
    def visit_enum_field(self, f:EnumFieldModel):
        if self.phase == 0:
            if not f in self.bound_m.keys():
                bounds = VariableBoundEnumModel(f)
                self.bound_m[f] = bounds
                
                
