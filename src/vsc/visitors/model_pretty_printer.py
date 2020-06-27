'''
Created on Apr 28, 2020

@author: ballance
'''
'''
Created on Apr 28, 2020

@author: ballance
'''

from _io import StringIO

import vsc.model as vm
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.unary_expr_type import UnaryExprType


class ModelPrettyPrinter(ModelVisitor):

    def __init__(self):
        self.out = StringIO()
        self.ind = ""
        self.print_values = False
        
    def do_print(self, m, print_values=False):
        self.ind = ""
        self.print_values = print_values
        self.out = StringIO()
        
        m.accept(self)
        
        return self.out.getvalue()
    
    @staticmethod
    def print(m, print_values=False):
        p = ModelPrettyPrinter()
        return p.do_print(m, print_values)
    
    def write(self, s):
        self.out.write(s)
        
    def writeln(self, l):
        self.out.write(self.ind + l + "\n")
        
    def inc_indent(self):
        self.ind += " "*4
        
    def dec_indent(self):
        self.ind = self.ind[4:]
    
    def visit_constraint_block(self, c:vm.ConstraintBlockModel):
        self.writeln("constraint " + c.name + " {")
        self.inc_indent()
        for stmt in c.constraint_l:
            stmt.accept(self)
        self.dec_indent()
        self.writeln("}")
        
    def visit_constraint_expr(self, c:ConstraintExprModel):
        self.write(self.ind)
        c.e.accept(self)
        self.write(";\n")
        
    def visit_constraint_foreach(self, f:ConstraintForeachModel):
        self.write(self.ind + "foreach (")
        f.lhs.accept(self)
        self.write("[i]) {\n")
        self.inc_indent()
        for s in f.constraint_l:
            s.accept(self)
        self.dec_indent()
        self.writeln("}")
        
    def visit_constraint_if_else(self, c:vm.ConstraintIfElseModel):
        self.write(self.ind + "if (")
        c.cond.accept(self)
        self.write(") {\n")
        self.inc_indent()
        c.true_c.accept(self)
        self.dec_indent()
        
        if c.false_c is not None:
            self.writeln("} else {")
            self.inc_indent()
            c.false_c.accept(self)
            self.dec_indent()
            
        self.writeln("}")
        
    def visit_constraint_implies(self, c:vm.ConstraintImpliesModel):
        self.write(self.ind)
        c.cond.accept(self)
        self.write(" -> {")

        for sc in c.constraint_l:
            sc.accept(self)
            
        self.write("}\n")
        
    def visit_expr_array_subscript(self, s):
        s.lhs.accept(self)
        self.write("[")
        s.rhs.accept(self)
        self.write("]")
        
    def visit_expr_array_sum(self, s):
        ModelVisitor.visit_expr_array_sum(self, s)

    def visit_expr_bin(self, e:vm.ExprBinModel):
        if e.lhs is None or e.rhs is None:
            print("op: " + str(e.op))
        self.write("(")
        e.lhs.accept(self)
        self.write(" " + vm.BinExprType.toString(e.op) + " ")
        e.rhs.accept(self)
        self.write(")")
        
    def visit_expr_in(self, e:vm.ExprInModel):
        e.lhs.accept(self)
        self.write(" in [")
        for i,r in enumerate(e.rhs.rl):
            r.accept(self)
            if i+1 < len(e.rhs.rl):
                self.write(", ")
                
        self.write("]")
        
    def visit_expr_literal(self, e : vm.ExprLiteralModel):
        self.write(str(int(e.val())))
        
    def visit_expr_fieldref(self, e : vm.ExprFieldRefModel):
        if self.print_values and hasattr(e.fm, "is_used_rand") and not e.fm.is_used_rand:
            if isinstance(e.fm, FieldArrayModel):
                self.write("[")
                for i,f in enumerate(e.fm.field_l):
                    if i>0:
                        self.write(", ")
                    self.write(str(int(f.get_val())))
                self.write("]")
            else:
                self.write(str(int(e.fm.get_val())))
        else:
            self.write(e.fm.fullname)
        
    def visit_expr_unary(self, e : vm.ExprUnaryModel):
        print("PrettyPrinter::visit_expr_unary")
        self.write(UnaryExprType.toString(e.op))
        self.write("(")
        e.expr.accept(self)
        self.write(")")
        
    def visit_scalar_field(self, f:FieldScalarModel):
        self.write(f.name)

