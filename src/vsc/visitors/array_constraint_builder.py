'''
Created on May 18, 2020

@author: ballance
'''

from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.model_visitor import ModelVisitor
from vsc.visitors.constraint_copy_builder import ConstraintCopyBuilder,\
    ConstraintCollector
from typing import Dict, Set
from vsc.model.field_model import FieldModel
from vsc.model.expr_model import ExprModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.visitors.constraint_override_visitor import ConstraintOverrideVisitor
from vsc.model.constraint_scope_model import ConstraintScopeModel


class ArrayConstraintBuilder(ConstraintOverrideVisitor):
    
    def __init__(self):
        super().__init__()
        self.index_set : Set[FieldModel] = set()
        
    @staticmethod
    def build(m):
        builder = ArrayConstraintBuilder()
        m.accept(builder)

        return builder.constraints
    
    def visit_constraint_foreach(self, f:ConstraintForeachModel):
        # Instead of just performing a straight copy, expand
        # the constraints
#        ret = f.clone()
        scope = ConstraintScopeModel()
        with ConstraintCollector(self, scope):
            # TODO: need to be a bit more flexible in getting the size
        
            size = int(f.lhs.fm.size.get_val())
            print("size=" + str(size))
            self.index_set.add(f.index)
            for i in range(size):
                f.index.set_val(i)
                # TODO: 
                for c in f.constraint_l:
                    c.accept(self)
            self.index_set.remove(f.index)
        
        self.override_constraint(scope)
            
#        self.constraints.append(ret)
        
    def visit_expr_fieldref(self, e : ExprFieldRefModel):
        if e.fm in self.index_set:
            # Replace the index with the appropriate literal value
            self._expr = ExprLiteralModel(int(e.fm.get_val()), False, 32)
        else:
            ConstraintCopyBuilder.visit_expr_fieldref(self, e)
        