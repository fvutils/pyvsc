'''
Created on Mar 18, 2022

@author: mballance
'''

import typeworks
from vsc2.impl.ctor import Ctor
from vsc2.impl.constraint_decl import ConstraintDecl

class ConstraintDecoratorImpl(typeworks.RegistrationDecoratorBase):
    """Constraint decorator implementation"""
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        decl = ConstraintDecl(T.__name__, T)
        typeworks.DeclRgy.push_decl(ConstraintDecoratorImpl, decl)

        return T
        