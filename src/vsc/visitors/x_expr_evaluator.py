'''
Created on Feb 5, 2022

@author: mballance
'''
from vsc.model.bin_expr_type import BinExprType
from vsc.model.enum_field_model import EnumFieldModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.value_scalar import ValueScalar
from vsc.visitors.expr2field_visitor import Expr2FieldVisitor


class XExprEvaluator(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self.is_x = False
        self.val = None
        self.debug = False
        
    def eval(self, e):
        e.accept(self)
        return (self.is_x, self.val)
    
    def visit_expr_bin(self, e:ExprBinModel):
        if self.debug:
            print("visit_expr_bin: op=%s" % str(e.op))
        e.lhs.accept(self)
        lhs_is_x = self.is_x
        lhs_val = self.val
        
        e.rhs.accept(self)
        rhs_is_x = self.is_x
        rhs_val = self.val

        if e.op == BinExprType.Add:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val + rhs_val)
        elif e.op == BinExprType.And:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val & rhs_val)
        elif e.op == BinExprType.Or:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val | rhs_val)
        elif e.op == BinExprType.Le:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val <= rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Lt:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val < rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Ge:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val >= rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Gt:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val > rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Eq:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val == rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Ne:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                if self.debug:
                    print("lhs=%d rhs=%d" % (int(lhs_val), int(rhs_val)))
                if lhs_val != rhs_val:
                    self.val = ValueScalar(1)
                else:
                    self.val = ValueScalar(0)
        elif e.op == BinExprType.Sub:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val - rhs_val)
        elif e.op == BinExprType.Div:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val / rhs_val)
        elif e.op == BinExprType.Mul:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val * rhs_val)
        elif e.op == BinExprType.Mod:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val % rhs_val)
        elif e.op == BinExprType.Sll:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val << rhs_val)
        elif e.op == BinExprType.Srl:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val >> rhs_val)
        elif e.op == BinExprType.Xor:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = (lhs_val ^ rhs_val)
        elif e.op == BinExprType.Not:
            if lhs_is_x or rhs_is_x:
                self.is_x = True
                self.val = None
            else:
                self.is_x = False
                self.val = ~lhs_val
        else:
            print("Unhandled op %s" % str(e.op))

        if self.debug:            
            print("    result: is_x=%s val=%d" % (str(self.is_x), int(self.val)))
                    
    def visit_expr_fieldref(self, e : ExprFieldRefModel):
        e.fm.accept(self)
        
    def visit_expr_array_subscript(self, s : ExprArraySubscriptModel):
        # Need to get field
        field : FieldArrayModel = Expr2FieldVisitor().field(s.lhs)
        if field.is_used_rand:
            self.is_x = True
            self.val = None
        else:
            self.is_x = False
            field.accept(self)
            
    def visit_expr_in(self, e):
        e.lhs.accept(self)
        
        if self.is_x:
            self.val = None
        else:
            # TODO: for now, consider 'in' to be an x-producing expression
            self.is_x = True
        
    def visit_expr_literal(self, e : ExprLiteralModel):
        self.is_x = False
        self.val = e.val()
    
    def visit_scalar_field(self, f:FieldScalarModel):
        if f.is_used_rand:
            self.is_x = True
            self.val = None
        else:
            self.is_x = False
            self.val = f.get_val()
            
    def visit_enum_field(self, f:EnumFieldModel):
        if f.is_used_rand:
            self.is_x = True
            self.val = None
        else:
            self.is_x = False
            self.val = f.get_val()
        
    def visit_field_bool(self, f):
        if f.is_used_rand:
            self.is_x = True
            self.val = None
        else:
            self.is_x = False
            self.val = f.get_val()

