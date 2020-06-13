'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.field_model import FieldModel
from typing import List
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.composite_field_model import CompositeFieldModel

class FieldScalarArrayModel(CompositeFieldModel):
    """All arrays are processed as if they were variable size."""
    
    def __init__(self, name, 
                 width,
                 is_signed,
                 is_rand,
                 is_rand_sz):
        super().__init__(name, is_rand)
        self.width = width
        self.is_signed = is_signed
        self.is_rand_sz = is_rand_sz
        self.size = FieldScalarModel(
            "size",
            32,
            False,
            is_rand_sz)
#        self.size.set_val(size)

        # Either the field creator or the model builder
        # is responsible for creating fields
#         if size > 0:       
#             for i in range(size):
#                 self.add_field(FieldScalarModel(
#                     "[" + str(i) + "]",
#                     width,
#                     is_signed,
#                     is_rand))
        
        # TODO: array properties, such as product, 
        # are actually expressions
        # Need some notion to deal with references
        # to expressions that are built on-demand
        
    def pre_randomize(self):
        # Set the size field for arrays that don't
        # have a random size
        if not self.is_rand_sz:
            self.size.set_val(len(self.field_l))
        CompositeFieldModel.pre_randomize(self)
        
    def add_field(self) -> FieldScalarModel:
        fid = len(self.field_l)
        return super().add_field(FieldScalarModel(
            self.name + "[" + str(fid) + "]",
            self.width,
            self.is_signed,
            self.is_declared_rand))
        
    def build(self, builder):
        # Called before randomization
        self.size.set_val(int(len(self.field_l)))
        super().build(builder)
        
    def accept(self, v):
        v.visit_field_scalar_array(self)
