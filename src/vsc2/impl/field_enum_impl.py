'''
Created on May 25, 2022

@author: mballance
'''
from libvsc.core import Context

from vsc2.impl.ctor import Ctor
from vsc2.impl.field_modelinfo import FieldModelInfo
from vsc2.impl.field_base_impl import FieldBaseImpl


class FieldEnumImpl(FieldBaseImpl):
    
    def __init__(self, name, lib_field, e_t):
        super().__init__(name, lib_field)
        ctxt : Context = Ctor.inst().ctxt()
        pass
    
    def get_val(self):
        pass
    
    def set_val(self, v):
        pass
    
    @property
    def val(self):
        pass
    