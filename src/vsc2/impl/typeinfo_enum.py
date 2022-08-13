'''
Created on Jul 4, 2022

@author: mballance
'''
from vsc2.impl.typeinfo_vsc import TypeInfoVsc

class TypeInfoEnum(TypeInfoVsc):
    
    def __init__(self, info, kind, e_info):
        super().__init__(kind, lib_typeobj)
        self._e_info = e_info
        
    @property
    def e_info(self):
        return self._e_info

    @e_info.setter
    def e_info(self, val):
        self._e_info = val
    
    @staticmethod
    def get(info):
        if not hasattr(info, TypeInfoVsc.ATTR_NAME):
            setattr(info, TypeInfoVsc.ATTR_NAME, TypeInfoEnum(info))
        return getattr(info, TypeInfoVsc.ATTR_NAME)