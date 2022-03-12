'''
Created on Mar 11, 2022

@author: mballance
'''
from libvsc import core

class Ctor():
    
    _inst = None
    
    def __init__(self):
        self._ctxt = core.Context.inst()
        pass
    
    def ctxt(self):
        return self._ctxt
    
    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = Ctor()
        return cls._inst
        