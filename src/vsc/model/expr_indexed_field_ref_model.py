

# Created on Mar 6, 2020
#
# @author: ballance

from vsc.model.expr_model import ExprModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel

class ExprIndexedFieldRefModel(ExprModel):
    
    def __init__(self,
                 root : ExprModel,
                 idx_t):
        super().__init__()
        
        if not isinstance(root, (ExprFieldRefModel,ExprArraySubscriptModel)):
            raise Exception("unsupported root for an indexed reference")
        
        self.root = root
        self.idx_t = idx_t
        
    def get_target(self, root=None):
        ret = root if root is not None else self.root.fm
        for i in self.idx_t:
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
        