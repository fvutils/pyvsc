'''
Created on May 8, 2021

@author: mballance
'''
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_cond_model import ExprCondModel
from vsc.model.expr_dynamic_model import ExprDynamicModel
from vsc.model.expr_model import ExprModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.expr_unary_model import ExprUnaryModel


class RetargetIndexedCoverpointTarget(ModelVisitor):
    """Retarget indexed reference-path expressions to a specific target (covergroup)"""
    
    def __init__(self, cg, root):
        super().__init__()
        self.cg = cg
        self.root = root
        self._expr = None
        
    def retarget(self, target) -> ExprModel:
        target.accept(self)
        return self._expr
        
    def expr(self, e):
        self._expr = None
        e.accept(self)
        return self._expr
        
    def visit_expr_array_product(self, s):
        self._expr = s
        
    def visit_expr_array_sum(self, s):
        self._expr = s

    def visit_expr_bin(self, e : ExprBinModel):
        lhs = self.expr(e.lhs)
        rhs = self.expr(e.rhs)
        self._expr = ExprBinModel(
            lhs,
            e.op,
            rhs)
        
    def visit_expr_cond(self, e : ExprCondModel):
        c = self.expr(e.cond_e)
        t = self.expr(e.true_e)
        f = self.expr(e.false_e)
        self._expr = ExprCondModel(c, t, f)
        
    def visit_expr_dynamic(self, e : ExprDynamicModel):
        self._expr = e
    
    def visit_expr_fieldref(self, e):
        self._expr = e
    
    def visit_expr_indexed_fieldref(self, e):
        # Locate the target and construct a new fieldref
        r = self.root
        for i in e.idx_t[1:]:
            r = r.field_l[i]
        self._expr = ExprFieldRefModel(r)
    
    def visit_expr_range(self, r):
        lhs = self.expr(r.lhs)
        rhs = self.expr(r.rhs)
        self._expr = ExprRangeModel(lhs, rhs)
    
    def visit_expr_rangelist(self, r):
        rl = []
        for ri in r.rl:
            rl.append(self.expr(ri))
        self._expr = ExprRangelistModel(rl)

    def visit_expr_array_subscript(self, s):
        self._expr = ExprArraySubscriptModel(
            s.lhs,
            self.expr(s.rhs))

    def visit_expr_in(self, e):
        lhs = self.expr(e.lhs)
        rhs = self.expr(e.rhs)
        self._expr = ExprInModel(lhs, rhs)
        
    def visit_expr_literal(self, e):
        self._expr = e
    
    def visit_expr_partselect(self, e):
        lhs = self.expr(e.lhs)
        upper = self.expr(e.upper)
        lower = self.expr(e.lower) if e.lower is not None else None
        self._expr = ExprPartselectModel(lhs, upper, lower)
            
    def visit_expr_unary(self, e):
        ec = self.expr(e.expr)
        self._expr = ExprUnaryModel(e.op, ec)
