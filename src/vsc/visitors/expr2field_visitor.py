'''
Created on Jun 25, 2021

@author: mballance
'''
from vsc.model.model_visitor import ModelVisitor
from vsc.model.expr_model import ExprModel
from vsc.model.expr_indexed_field_ref_model import ExprIndexedFieldRefModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel

class Expr2FieldVisitor(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self.fm = None
        
    def field(self, e : ExprModel):
        e.accept(self)
        
        if self.fm is None:
            from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
            raise Exception("Failed to obtain field from expression %s" % (
                ModelPrettyPrinter.print(e)))
        return self.fm
        
    def visit_expr_fieldref(self, e):
        self.fm = e.fm
        
    def visit_expr_indexed_fieldref(self, e : ExprIndexedFieldRefModel):
        self.fm = e.get_target()
        
    def visit_expr_array_subscript(self, s : ExprArraySubscriptModel):
        self.fm = s.subscript()
        