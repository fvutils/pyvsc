'''
Created on Jul 4, 2022

@author: mballance
'''
from vsc2.impl.field_base_impl import FieldBaseImpl


class FieldListScalarImpl(FieldBaseImpl):
    
    def __init__(self, name, lib_field):
        super().__init__(name, lib_field)
        
    @property
    def size(self):
        pass
    
    def append(self, v):
        pass
    
    def __getitem__(self, it):
        pass
        