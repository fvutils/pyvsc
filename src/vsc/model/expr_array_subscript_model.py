'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.expr_model import ExprModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel

class ExprArraySubscriptModel(ExprModel):
    
    def __init__(self, lhs : 'FieldArrayModel', rhs : ExprModel):
        super().__init__()
        self.lhs = lhs
        self.rhs = rhs
        
    def build(self, btor, ctx_width=-1):
        from vsc.visitors.refs_used_rand_visitor import refs_used_rand
        if not isinstance(self.lhs, ExprFieldRefModel):
            # An array reached through an object (`objs[i].arr[j]`).
            from vsc.model.expr_indexed_field_ref_model import (
                ref_alternatives, is_symbolic, build_select)
            alts = ref_alternatives(self)
            if is_symbolic(alts):
                return build_select(btor, alts)
            return alts[0][1].build(btor)
        if refs_used_rand(self.rhs):
            return self._build_select(btor)
        index = int(self.rhs.val())
        if isinstance(self.lhs, ExprFieldRefModel):
            fm = self.lhs.fm.field_l[index]
            return fm.build(btor)
        else:
            # TODO: support array slicing
            raise NotImplementedError("Cannot subscript an lvalue of type " + str(type(self.lhs)))
        
    def _build_select(self, btor):
        """``arr[idx]`` with a random ``idx``: the index has no value until the
        solve, so select symbolically,
        ``idx == 0 ? arr[0] : idx == 1 ? arr[1] : ... : arr[n-1]``,
        as the dv-solve back-end does."""
        elems = self.lhs.fm.field_l
        if len(elems) == 0:
            raise Exception("Variable index into the empty array %s" % (
                self.lhs.fm.name,))
        idx = self.rhs.build(btor)
        idx_w = idx.width
        n = len(elems)
        if n > (1 << idx_w):
            n = 1 << idx_w      # the index cannot reach the rest
        ret = elems[n - 1].build(btor)
        for i in range(n - 2, -1, -1):
            ret = btor.Cond(btor.Eq(idx, btor.Const(i, idx_w)),
                            elems[i].build(btor), ret)
        return ret

    def _type_index(self):
        """Index of an element whose type stands for the result's. A random
        index read before the solve may be out of range; the elements share
        one type, so element 0 serves."""
        from vsc.visitors.refs_used_rand_visitor import refs_used_rand
        if isinstance(self.lhs, ExprFieldRefModel) and refs_used_rand(self.rhs):
            return 0
        return int(self.rhs.val())

    def subscript(self):
        from vsc.model.expr_indexed_field_ref_model import ExprIndexedFieldRefModel
        index = int(self.rhs.val())
        if isinstance(self.lhs, ExprFieldRefModel):
            fm = self.lhs.fm
        elif isinstance(self.lhs, ExprIndexedFieldRefModel):
            fm = self.lhs.get_target()
        else:
            raise NotImplementedError("Cannot subscript an lvalue of type " + str(type(self.lhs)))
            
        if index < len(fm.field_l):
            return fm.field_l[index]
        else:
            raise Exception("List size: " + str(len(self.lhs.fm.field_l)) + " index: " + str(index))
        
        
    def _type_field(self):
        """A field whose type stands for the result's."""
        if isinstance(self.lhs, ExprFieldRefModel):
            return self.lhs.fm.field_l[self._type_index()]
        from vsc.model.expr_indexed_field_ref_model import ref_alternatives
        return ref_alternatives(self)[0][1]

    def is_signed(self):
        return self._type_field().is_signed
        
    def width(self):
        return self._type_field().width
        
    def accept(self, v):
        v.visit_expr_array_subscript(self)
        
    def val(self):
        index = int(self.rhs.val())
        if isinstance(self.lhs, ExprFieldRefModel):
            return self.lhs.fm.field_l[index].val()
        # After the solve every index has its value.
        from vsc.model.expr_indexed_field_ref_model import ref_alternatives
        return ref_alternatives(self, lambda _: False)[0][1].val()
        
    def getFieldModel(self):
        index = int(self.rhs.val())
        if isinstance(self.lhs, ExprFieldRefModel):
            return self.lhs.fm.field_l[index]
        else:
            # TODO: support array slicing
            raise NotImplementedError("Cannot subscript an lvalue of type " + str(type(self.lhs)))
        
