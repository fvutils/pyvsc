'''
Created on Mar 18, 2022

@author: mballance
'''
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo import TypeInfo

class RandClassTypeInfo(TypeInfo):
    
    def __init__(self, lib_typeobj):
        super().__init__(TypeKindE.RandClass, lib_typeobj)
        self._field_ctor_m = {}
        self._constraint_m = {}
        self._constraint_l = []
        self._field_typeinfo = []
        
    def addField(self, field_ti):
        self._lib_typeobj.addField(field_ti._lib_typeobj)
        self._field_typeinfo.append(field_ti)

