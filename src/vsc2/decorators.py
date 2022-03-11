'''
Created on Feb 26, 2022

@author: mballance
'''

from vsc2.impl.randobj_impl import RandObjImpl


def randobj(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        # No-argument form
        return RandObjImpl({})(args[0])
    else:
        return RandObjImpl(kwargs)
    