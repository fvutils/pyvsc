'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.field_model import FieldModel
from typing import List
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.enum_field_model import EnumFieldModel

class FieldArrayModel(FieldCompositeModel):
    """All arrays are processed as if they were variable size."""
    
    def __init__(self, 
                 name, 
                 is_scalar,
                 enums,
                 width,
                 is_signed,
                 is_rand,
                 is_rand_sz):
        super().__init__(name, is_rand)
        # width and is_signed only needed for scalar fields
        self.is_enum = (enums is not None)
        self.enums = enums
        self.is_scalar = is_scalar
        self.width = width
        self.is_signed = is_signed
        self.is_rand_sz = is_rand_sz
        # Holds a cached version of the sum constraint
        self.sum_expr_btor = None
        self.sum_expr = None
        
        self.size = FieldScalarModel(
            "size",
            32,
            False,
            is_rand_sz)
        
    def append(self, fm):
        super().add_field(fm)
        self.size.set_val(len(self.field_l))
        fm.is_declared_rand = self.is_declared_rand
        fm.rand_mode = self.is_declared_rand
        self.name_elems()
        
    def clear(self):
        self.field_l.clear()
        self.size.set_val(0)

    def pop(self, idx=0):
        self.field_l.pop(idx)
        self.size.set_val(len(self.field_l))
        self.name_elems()
        
    def name_elems(self):
        """Apply an index-based name to all fields"""
        for i,f in enumerate(self.field_l):
            f.name = self.name + "[" + str(i) + "]"
        
    def pre_randomize(self):
        # Set the size field for arrays that don't
        # have a random size
        if not self.is_rand_sz:
            self.size.set_val(len(self.field_l))
        FieldCompositeModel.pre_randomize(self)
        
    def post_randomize(self):
        FieldCompositeModel.post_randomize(self)
        self.sum_expr = None
        self.sum_expr_btor = None
        
    def add_field(self) -> FieldScalarModel:
        fid = len(self.field_l)
        if self.is_enum:
            return super().add_field(EnumFieldModel(
                self.name + "[" + str(fid) + "]",
                self.enums,
                self.is_declared_rand))
        else:
            return super().add_field(FieldScalarModel(
                self.name + "[" + str(fid) + "]",
                self.width,
                self.is_signed,
                self.is_declared_rand))
        # Update the size
        self.size.set_val(len(self.field_l))
        
    def build(self, builder):
        # Called before randomization
        self.size.set_val(int(len(self.field_l)))
        super().build(builder)
        
    def get_sum_expr(self):
        if self.sum_expr is None:
            # Build
            ret = None
            for f in self.field_l:
                if ret is None:
                    ret = ExprFieldRefModel(f)
                else:
                    ret = ExprBinModel(
                        ret,
                        BinExprType.Add,
                        ExprFieldRefModel(f))
                
            if ret is None:
                ret = ExprLiteralModel(0, False, 32)
            self.sum_expr = ret
            
        return self.sum_expr
        
    def build_sum_expr(self, btor):
        if self.sum_expr_btor is None:
            self.sum_expr_btor = self.get_sum_expr().build(btor)
        return self.sum_expr_btor
        
    def accept(self, v):
        v.visit_field_scalar_array(self)
