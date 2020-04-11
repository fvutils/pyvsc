

# Created on Mar 27, 2020
#
# @author: ballance

from typing import Set, List

from vsc.model.field_model import FieldModel
from vsc.model.rand_gen_data import RandGenData


class EnumFieldModel(FieldModel):
    
    def __init__(self,
                 name : str,
                 enums : List[int],
                 is_rand : bool):
        super().__init__(name)
        self.enums = enums
        self.is_declared_rand = is_rand
        self.is_used_rand = is_rand
        self.var = None
        self.val = enums[0]
        self.randgen_data = None
        self.rand_if = None
        
        # TODO: a bit simplistic
        self.width = 32
        self.is_signed = True
        
        
    def set_used_rand(self, is_rand, level):
        self.is_used_rand = (is_rand and (self.is_declared_rand or level==0))
        if self.is_used_rand and self.randgen_data is None:
            self.randgen_data = RandGenData(self.width, self.is_signed)
            self.randgen_data.bag = self.enums
            
    def dispose(self):
        self.var = None
        
    def accept(self, v):
        v.visit_enum_field(self)
        
    def build(self, btor):
        if self.is_used_rand:
            sort = btor.BitVecSort(self.width)
            self.var = btor.Var(sort)
        else:
            self.var = btor.Const(self.val, self.width)
        return self.var
    
    def __str__(self):
        return "EnumFieldModel(" + self.get_full_name() + ")"

    def get_constraints(self, constraint_l):
        pass

    def pre_randomize(self):
        if self.rand_if is not None:
            self.rand_if.do_pre_randomize()
    
    def set_val(self, val):
        self.val = val
        
    def get_val(self):
        return self.val
    
    def post_randomize(self):
        if self.var is not None:
            val = 0
            for b in self.var.assignment:
                val <<= 1
                if b == '1':
                    val |= 1
            self.set_val(val)
            
        if self.rand_if is not None:
            self.rand_if.do_post_randomize()
    