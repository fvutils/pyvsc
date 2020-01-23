'''
Created on Jan 22, 2020

@author: ballance
'''
from vsc.model.model_visitor import ModelVisitor
from vsc.model.field_model import FieldModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.rand_info import RandInfo
from builtins import set
from vsc.model.rand_set import RandSet

class RandInfoBuilder(ModelVisitor):
    
    def __init__(self):
        super().__init__()
        self._pass = 0
        self._field_s = set()
        self._active_constraint = None
        self._active_randset = None
        self._randset_l = []
        self._randset_field_m = {} # map<field,randset>
        self._constraint_s = []
        
    @staticmethod
    def build(
            field_model_l : [FieldModel],
            constraint_l : [ConstraintModel]) ->RandInfo:
        builder = RandInfoBuilder()

        # First, collect all the fields
        builder._pass = 0
        for fm in field_model_l:
            fm.accept(builder)
            
        # Now, build the randset
        builder._pass = 1
        for fm in field_model_l:
            fm.accept(builder)
        for c in constraint_l:
            c.accept(builder)
            
        return RandInfo(builder._randset_l, list(builder._field_s))
    
    def visit_constraint_block(self, c):
        # Null out the randset on entry to a constraint block
        self._active_randset = None
        self._constraint_s.append(c)
        super().visit_constraint_block(c)
        self._constraint_s.clear()
        
    def visit_constraint_stmt_enter(self, c):
        if self._pass == 1 and len(self._constraint_s) == 1:
            self._active_randset = None
        self._constraint_s.append(c)
        super().visit_constraint_stmt_enter(c)
        
    def visit_constraint_stmt_leave(self, c):
        self._constraint_s.pop()
        if self._pass == 1 and len(self._constraint_s) == 1:
            if self._active_randset is not None:
                self._active_randset.add_constraint(c)
            else:
                print("TODO: handle no-reference constraint: " + str(c))
        super().visit_constraint_stmt_leave(c)
    
    def visit_constraint_expr(self, c):
        super().visit_constraint_expr(c)

    def visit_expr_fieldref(self, e):
        if self._pass == 1:
            # During pass 1, build out randsets based on constraint
            # relationships
            if self._active_randset is None:
                if e.fm in self._randset_field_m.keys():
                    self._active_randset = self._randset_field_m[e.fm]
                else:
                    self._active_randset = RandSet()
                    self._randset_l.append(self._active_randset)
                    
            if not e.fm in self._randset_field_m.keys():
                self._active_randset.add_field(e.fm)
                self._randset_field_m[e.fm] = self._active_randset
            if e.fm in self._field_s:
                self._field_s.remove(e.fm)

        super().visit_expr_fieldref(e)

    def visit_scalar_field(self, f):
        if self._pass == 0:
            self._field_s.add(f)
    