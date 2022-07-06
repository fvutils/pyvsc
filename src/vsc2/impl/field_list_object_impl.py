'''
Created on Jul 2, 2022

@author: mballance
'''
from vsc2.impl.field_base_impl import FieldBaseImpl
from vsc2.impl.ctor import Ctor

class FieldListObjectImpl(FieldBaseImpl):

    def __init__(self, name, typeinfo, lib_field):
        super().__init__(name, typeinfo, lib_field)
        self._elems = []
        
    @property
    def size(self):
        ctor = Ctor.inst()
        
        if ctor.expr_mode():
            return 
            if ctor.is_type_mode():
                raise Exception("TODO")
            else:
                pass
            
    def __len__(self):
        ctor = Ctor.inst()
        if ctor.expr_mode():
            raise Exception('len cannot be used in constraints')
        else:
            return self._modelinfo._lib_obj.getSize()
        
    def append(self, v):
        self._elems.append(v)
#        self._modelinfo._lib_obj.push_back()
        print("TODO: append")
    