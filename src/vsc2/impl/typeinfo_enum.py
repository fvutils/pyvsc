'''
Created on Jul 4, 2022

@author: mballance
'''
from vsc2.impl.typeinfo import TypeInfo

class TypeInfoEnum(TypeInfo):
    
    def __init__(self, kind, lib_typeobj, e_info):
        super().__init__(kind, lib_typeobj)
        self._e_info = e_info