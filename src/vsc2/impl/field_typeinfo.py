'''
Created on Apr 6, 2022

@author: mballance
'''
from vsc2.impl.typeinfo import TypeInfo
from vsc2.impl.type_kind_e import TypeKindE

class FieldTypeInfo(TypeInfo):
    
    def __init__(self, name, idx, lib_typeobj, ctor):
        super().__init__(TypeKindE.Field, lib_typeobj)
        self._name = name
        self._idx = idx
        self._ctor = ctor