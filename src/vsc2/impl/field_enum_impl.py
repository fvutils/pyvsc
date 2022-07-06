'''
Created on May 25, 2022

@author: mballance
'''
from libvsc.core import Context

from vsc2.impl.ctor import Ctor
from vsc2.impl.field_modelinfo import FieldModelInfo
from vsc2.impl.field_base_impl import FieldBaseImpl


class FieldEnumImpl(FieldBaseImpl):
    
    def __init__(self, name, typeinfo, lib_field):
        super().__init__(name, typeinfo, lib_field)
        ctxt : Context = Ctor.inst().ctxt()
        pass
    
    def get_val(self):
        val = self._modelinfo._lib_obj.val().val_i()
        val_e = self._modelinfo._typeinfo._e_info.v2e_m[val]
        return val_e
    
    def set_val(self, v):
        val = self._modelinfo._typeinfo._e_info.e2v_m[v]
        self._modelinfo._lib_obj.val().set_val_i(val)
    
    @property
    def val(self):
        val = self._modelinfo._lib_obj.val().val_i()
        val_e = self._modelinfo._typeinfo._e_info.v2e_m[val]
        return val_e
    
    @val.setter
    def val(self, v):
        val = self._modelinfo._typeinfo._e_info.e2v_m[v]
        self._modelinfo._lib_obj.val().set_val_i(val)
    