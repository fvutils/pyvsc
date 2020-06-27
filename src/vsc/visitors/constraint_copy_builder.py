'''
Created on May 18, 2020

@author: ballance
'''
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.constraint_scope_model import ConstraintScopeModel

class ConstraintCollector(object):
    """Creates a copy of a given constraints"""
    
    def __init__(self, builder, scope):
        self._builder = builder
        self._scope = scope
        self._constraints = None
        self._expr = None
        pass
    
    def __enter__(self):
        self._constraints = self._builder.constraints
        self._builder.constraints = []
        self._builder.do_copy_level += 1
        
    def __exit__(self, t, v, tb):
        for c in self._builder.constraints:
            self._scope.constraint_l.append(c)
        self._builder.constraints = self._constraints
        self._builder.do_copy_level -= 1


class ConstraintCopyBuilder(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self.constraints : List[ConstraintBlockModel] = []
        self.constraints_s : List[List[ConstraintModel]] = []
        self.do_copy_level = 0
        
    @staticmethod
    def copy(m):
        copier = ConstraintCopyBuilder()
        copier.do_copy_level += 1
        m.accept(copier)
        copier.do_copy_level -= 1
        return copier.constraints
        
    def visit_constraint_block(self, c:ConstraintBlockModel):
        if self.do_copy_level > 0:
            ret = ConstraintBlockModel(c.name)
            ret.enabled = c.enabled
            ret.is_dynamic = c.is_dynamic

            with ConstraintCollector(self, ret):
                for cs in c.constraint_l:
                    cs.accept(self)
            self.constraints.append(ret)
        else:
            super().visit_constraint_block(c)
        
    def visit_constraint_expr(self, c:ConstraintExprModel):
        if self.do_copy_level > 0:
            ret = ConstraintExprModel(self.expr(c.e))
            self.constraints.append(ret)
        else:
            super().visit_constraint_expr(c)
        
    def visit_constraint_foreach(self, f:ConstraintForeachModel):
        if self.do_copy_level > 0:
            ret = f.clone()
        
            with ConstraintCollector(self, ret):
                for cs in f.constraint_l:
                    cs.accept(self)
        
            self.constraints.append(ret)
        else:
            super().visit_constraint_foreach(f)
        
    def visit_constraint_if_else(self, c:ConstraintIfElseModel):
        from .model_pretty_printer import ModelPrettyPrinter
        if self.do_copy_level > 0:
            ret = ConstraintIfElseModel(self.expr(c.cond))
           
            ret.true_c = ConstraintScopeModel() 
            with ConstraintCollector(self, ret.true_c):
                for cs in c.true_c.constraint_l:
                    cs.accept(self)
                
            if c.false_c is not None:
                ret.false_c = ConstraintScopeModel()
                with ConstraintCollector(self, ret.false_c):
                    for cs in c.false_c.constraint_l:
                        cs.accept(self)

            self.constraints.append(ret)
        else:
            super().visit_constraint_if_else(c)
        
    def visit_constraint_implies(self, c:ConstraintImpliesModel):
        if self.do_copy_level > 0:
            ret = ConstraintImpliesModel(self.expr(c.cond))
        
            with ConstraintCollector(self, ret):
                for cs in c.constraint_l:
                    cs.accept(self)
        
            self.constraints.append(ret)
        else:
            super().visit_constraint_implies(c)
        
    def visit_constraint_soft(self, c:ConstraintSoftModel):
        if self.do_copy_level > 0:
            ret = ConstraintSoftModel(self.expr(c.expr))
            self.constraints.append(ret)
        else:
            super().visit_constraint_soft(c)
        
    def visit_constraint_unique(self, c:ConstraintUniqueModel):
        if self.do_copy_level > 0:
            self.constraints.append(c.clone())
        else:
            super().visit_constraint_unique(c)
        
    def visit_expr_bin(self, e:ExprBinModel):
        from .model_pretty_printer import ModelPrettyPrinter
        if self.do_copy_level > 0:
            self._expr = ExprBinModel(
                self.expr(e.lhs),
                e.op,
                self.expr(e.rhs))
        else:
            super().visit_expr_bin(e)
        
    def visit_expr_fieldref(self, e):
        # Default to pass-through
        if self.do_copy_level > 0:
            self._expr = e
        else:
            super().visit_expr_fieldref(e)
        
    def visit_expr_literal(self, e):
        if self.do_copy_level > 0:
            self._expr = e
        else:
            super().visit_expr_literal(e)
        
    def visit_expr_array_subscript(self, s):
        if self.do_copy_level > 0:
            self._expr = ExprArraySubscriptModel(
                self.expr(s.lhs),
                self.expr(s.rhs))
        else:
            super().visit_expr_array_subscript(s)
            
        
    def expr(self, e):
        self._expr = None
        e.accept(self)
        return self._expr
        