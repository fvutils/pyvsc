'''
Created on Nov 5, 2020

@author: mballance
'''
from vsc.model.model_visitor import ModelVisitor

class IsNonRandExprVisitor(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self._is_nonrand = True
        
        
    def is_nonrand(self, e) -> bool:
        self._is_nonrand = True
        e.accept(self)
        return self._is_nonrand

    def visit_expr_fieldref(self, e):
        # One random field makes the expression random, wherever it is.
        if e.fm.is_used_rand:
            self._is_nonrand = False

    def visit_expr_array_sum(self, e):
        self._array(e.arr)

    def visit_expr_array_product(self, e):
        self._array(e.arr)

    def _array(self, arr):
        # A random-size array has no elements before the solve, so its size
        # field must be checked as well as the elements.
        if getattr(arr, "is_used_rand", False) \
                or getattr(arr.size, "is_used_rand", False) \
                or any(getattr(f, "is_used_rand", False) for f in arr.field_l):
            self._is_nonrand = False
        
        