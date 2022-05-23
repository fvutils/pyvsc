'''
Created on May 22, 2022

@author: mballance
'''
from vsc2.impl import ctor
from vsc2.impl.ctor import Ctor

class RandObjImpl(object):

    @staticmethod    
    def init(self, base, *args, **kwargs):
        print("init")
        base(self, *args, *kwargs)
        pass

    @staticmethod    
    def __getattribute__(self, attr):
        ret = object.__getattribute__(self, attr)
        pass
    
    @staticmethod
    def __setattr__(self, field, val):
        pass
    
    
    @staticmethod
    def randomize(self, **kwargs):
        pass
    
    class RandWithClosure(object):
        
        def __init__(self, obj):
            self._obj = obj
        
        def __enter__(self):
            Ctor.inst().push_expr_mode()
            return self._obj
    
        def __exit__(self, t, v, tb):
            Ctor.inst().pop_expr_mode()
            pass
    
    @staticmethod
    def randomize_with(self, **kwargs):
        return RandObjImpl.RandWithClosure(self)
        pass
    
    @staticmethod
    def set_randstate(self, state):
        pass

    @staticmethod
    def get_randstate(self):
        pass

    
    @classmethod
    def addMethods(cls, T):
        base = T.__init__
        setattr(T, "__init__", lambda self, *args, **kwargs: RandObjImpl.init(self, base, *args, *kwargs))
        setattr(T, "randomize", cls.randomize)
        setattr(T, "randomize_with", cls.randomize_with)
        setattr(T, "set_randstate", cls.set_randstate)
        setattr(T, "get_randstate", cls.get_randstate)
    
    pass