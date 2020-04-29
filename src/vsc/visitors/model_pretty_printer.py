'''
Created on Apr 28, 2020

@author: ballance
'''
from vsc.model.unary_expr_type import UnaryExprType
'''
Created on Apr 28, 2020

@author: ballance
'''

import vsc.model as vm
from portaskela.visitors.model_visitor import ModelVisitor
from _io import StringIO


class ModelPrettyPrinter(ModelVisitor):

    def __init__(self):
        self.out = StringIO()
        self.ind = ""
    
    @staticmethod
    def print(m):
        p = ModelPrettyPrinter()
        m.accept(p)
        return p.out.getvalue()
    
    def write(self, s):
        self.out.write(s)
        
    def writeln(self, l):
        self.out.write(self.ind + l + "\n")
        
    def inc_indent(self):
        self.ind += " "*4
        
    def dec_indent(self):
        self.ind = self.ind[4:]
    
    def visit_constraint_block(self, c:vm.ConstraintBlockModel):
        self.writeln("constraint " + c.name + "{")
        self.inc_indent()
        for stmt in c.constraint_l:
            stmt.accept(self)
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

    def visit_expr_bin(self, e:vm.ExprBinModel):
        self.write("(")
        e.lhs.accept(self)
        self.write(" " + vm.BinExprType.toString(e.op) + " ")
        e.rhs.accept(self)
        self.write(")")
        
    def visit_expr_literal(self, e : vm.ExprLiteralModel):
        self.write(str(e.val()))
        
    def visit_expr_fieldref(self, e : vm.ExprFieldRefModel):
        self.write(e.fm.fullname)
        
    def visit_expr_unary(self, e : vm.ExprUnaryModel):
        print("PrettyPrinter::visit_expr_unary")
        self.write(UnaryExprType.toString(e.op))
        self.write("(")
        e.expr.accept(self)
        self.write(")")

