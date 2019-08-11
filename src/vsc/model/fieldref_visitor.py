'''
Created on Aug 10, 2019

@author: ballance
'''
from vsc.model.model_visitor import ModelVisitor
from builtins import set

class FieldrefVisitor(ModelVisitor):
    
    def __init__(self):
        self.ref_s = set()
    
    def visit_expr_fieldref(self, e):
        self.ref_s.add(e.fm)
        