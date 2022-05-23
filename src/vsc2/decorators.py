'''
Created on Feb 26, 2022

@author: mballance
'''

from vsc2.impl.constraint_decorator_impl import ConstraintDecoratorImpl
from vsc2.impl.rand_obj_decorator_impl import RandObjDecoratorImpl
from vsc2.impl.randclass_decorator_impl import RandClassDecoratorImpl


def constraint(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return ConstraintDecoratorImpl({})(args[0])
    else:
        return ConstraintDecoratorImpl(kwargs)

def randclass(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return RandClassDecoratorImpl({})(args[0])
    else:
        return RandClassDecoratorImpl(kwargs)
    
def randobj(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return RandObjDecoratorImpl({})(args[0])
    else:
        return RandObjDecoratorImpl(kwargs)
    
    
