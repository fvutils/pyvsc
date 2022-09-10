'''
Created on Apr 6, 2022

@author: mballance
'''

import typeworks
from .modelinfo import ModelInfo

class TypeInfoVsc(object):
    
    ATTR_NAME = "_vsc_typeinfo"
    
    def __init__(self, info, kind, inner=None):
        self._info = info
        self._kind = kind
        self._lib_typeobj = None
        self._inner = inner

    def createInst(
        self,
        modelinfo_p : ModelInfo, # Parent model info
        name, # Name, just for interest sake
        idx): # Index within the parent native object
        raise NotImplementedError("createInst not implemented for type-info %s" % str(type(self)))
    
    @property
    def lib_typeobj(self):
        return self._lib_typeobj
    
    @lib_typeobj.setter
    def lib_typeobj(self, val):
        self._lib_typeobj = val
        
    @property
    def info(self):
        return self._info
    
