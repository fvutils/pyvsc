'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.field_model import FieldModel
from typing import List
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.composite_field_model import CompositeFieldModel

class FieldScalarArrayModel(CompositeFieldModel):
    
    def __init__(self, name, 
                 width,
                 is_signed,
                 is_rand,
                 size=0):
        super().__init__(name, is_rand)
        self.size = FieldScalarModel(
            "size",
            32,
            False,
            False)
        self.size.set_val(size)
        
        for i in range(size):
            self.add_field(FieldScalarModel(
                "[" + str(i) + "]",
                width,
                is_signed,
                is_rand))
        
        # TODO: array properties, such as product, 
        # are actually expressions
        # Need some notion to deal with references
        # to expressions that are built on-demand
        
    def build(self, builder):
        # Called before randomization
        self.size.set_val(int(len(self.field_l)))
        super().build(builder)
