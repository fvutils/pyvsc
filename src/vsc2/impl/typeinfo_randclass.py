'''
Created on Mar 18, 2022

@author: mballance
'''
from typing import List

from .typeinfo_field import TypeInfoField
from .constraint_decl import ConstraintDecl
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo_vsc import TypeInfoVsc

class TypeInfoRandClass(TypeInfoVsc):
    
    def __init__(self, info, kind=TypeKindE.RandClass):
        super().__init__(info, kind)
        self._field_ctor_m = {}
        self._constraint_m = {}
        self._constraint_l = []
        self._field_typeinfo = []
        
    def addField(self, field_ti):
        self._lib_typeobj.addField(field_ti._lib_typeobj)
        self._field_typeinfo.append(field_ti)
        
    def getFields(self) -> List[TypeInfoField]:
        return self._field_typeinfo
        
    def addConstraint(self, c : ConstraintDecl):
        self._constraint_m[c.name] = c
        self._constraint_l.append(c)
        
    def addConstraints(self, c_l : List[ConstraintDecl]):
        for c in c_l:
            self.addConstraint(c)
            
    def getConstraints(self) -> List[ConstraintDecl]:
        return self._constraint_l
        
    @staticmethod
    def get(info) -> 'TypeInfoRandClass':
        if not hasattr(info, TypeInfoVsc.ATTR_NAME):
            setattr(info, TypeInfoVsc.ATTR_NAME, TypeInfoRandClass(info))
        return getattr(info, TypeInfoVsc.ATTR_NAME)

