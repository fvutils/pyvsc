'''
Created on Jun 23, 2022

@author: mballance
'''
import dataclasses
from vsc2.impl import ctor
from vsc2.impl.ctor import Ctor
from vsc2.coverage import coverpoint

class CovergroupDecoratorImpl(object):
    
    def __init__(self, kwargs):
        pass
    

    def __call__(self, T):
        Tp = dataclasses.dataclass(T, init=False)

        Ctor.inst().push_expr_mode()
        for f in dataclasses.fields(Tp):
            print("Field: %s" % f.name)
            if callable(f.type) and f.type != int:
                f.type(Tp)
        Ctor.inst().pop_expr_mode()

        pass    
