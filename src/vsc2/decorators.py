'''
Created on Feb 26, 2022

@author: mballance
'''

from vsc2.impl.randclass_impl import RandClassImpl

def constraint(T):
    return T

def randclass(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return RandClassImpl({})(args[0])
    else:
        return RandClassImpl(kwargs)
    