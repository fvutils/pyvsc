

# Created on Mar 6, 2020
#
# @author: ballance

from vsc.model.expr_model import ExprModel

class ExprIndexedFieldRefModel(ExprModel):
    
    def __init__(self,
                 base_fm : 'CompositeFieldModel',
                 idx_l):
        super().__init__()
        self.base_fm = base_fm
        self.idx_l = idx_l
        
    def get_target(self):
        ret = self.base_fm
        for i in self.idx_l:
            ret = ret.get_field(i)
            
        return ret
        
        
    def build(self, btor):
        return self.get_target().build(btor)
    
    def is_signed(self):
        return self.get_target().is_signed()
    
    def width(self):
        return self.get_target().width()
    
    def accept(self, v):
        v.visit_expr_indexed_fieldref(self)
        
    def val(self, parent=None): 
        return self.get_target().val
        
    def __str__(self):
        ret = "IndexedFieldRef: "
        f = self.base_fm
        for idx,i in enumerate(self.idx_l):
            ret += f[idx].name
            if i < len(self.idx_l):
                ret += "."
        return ret
    