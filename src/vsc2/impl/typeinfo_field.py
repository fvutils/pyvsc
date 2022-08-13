'''
Created on Apr 6, 2022

@author: mballance
'''
from vsc2.impl.typeinfo_vsc import TypeInfoVsc
from vsc2.impl.type_kind_e import TypeKindE

class TypeInfoField(TypeInfoVsc):
    
    def __init__(self, name, idx, lib_typeobj, ctor):
        super().__init__(None, TypeKindE.Field)
        self._name = name
        self._idx = idx
        self._ctor = ctor
        
        self.lib_typeobj = lib_typeobj

    @property        
    def name(self):
        return self._name