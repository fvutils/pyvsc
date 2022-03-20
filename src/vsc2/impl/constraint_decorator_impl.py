'''
Created on Mar 18, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from vsc2.impl.constraint_decl import ConstraintDecl

class ConstraintDecoratorImpl(object):
    """Constraint decorator implementation"""
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        decl = ConstraintDecl(T.__name__, T)
        Ctor.inst().push_constraint_decl(decl)

        return T
        