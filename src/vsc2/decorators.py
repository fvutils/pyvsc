'''
Created on Feb 26, 2022

@author: mballance
'''

from vsc2.impl.constraint_decorator_impl import ConstraintDecoratorImpl
from vsc2.impl.randclass_impl import RandClassImpl

def constraint(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return ConstraintDecoratorImpl({})(args[0])
    else:
        return ConstraintDecoratorImpl(kwargs)

def randclass(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return RandClassImpl({})(args[0])
    else:
        return RandClassImpl(kwargs)
    
