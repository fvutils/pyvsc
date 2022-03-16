'''
Created on Mar 11, 2022

@author: mballance
'''
from libvsc import core
from vsc2.impl.ctor_scope import CtorScope

class Ctor():
    
    _inst = None
    
    def __init__(self):
        self._ctxt = core.Context.inst()
        self._scope_s = []
        pass
    
    def ctxt(self):
        return self._ctxt
    
    def scope(self):
        if len(self._scope_s) > 0:
            return self._scope_s[-1]
        else:
            return None
        
    def push_scope(self, obj, field):
        s = CtorScope(obj, field)
        self._scope_s.append(s)
        return s
        
    def pop_scope(self):
        self._scope_s.pop()
    
    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = Ctor()
        return cls._inst
        