'''
Created on Apr 6, 2022

@author: mballance
'''

import typeworks

class TypeInfoVsc(object):
    
    ATTR_NAME = "_vsc_typeinfo"
    
    def __init__(self, info, kind, inner=None):
        self._info = info
        self._kind = kind
        self._lib_typeobj = None
        self._inner = inner
        
    @property
    def lib_typeobj(self):
        return self._lib_typeobj
    
    @lib_typeobj.setter
    def lib_typeobj(self, val):
        self._lib_typeobj = val
        
    @property
    def info(self):
        return self._info
    
