'''
Created on Mar 11, 2022

@author: mballance
'''
from libvsc import core
from libvsc.core import Context

from vsc2.impl.ctor import Ctor
from vsc2.impl.expr import Expr
from vsc2.impl.field_base_impl import FieldBaseImpl
from vsc2.impl.field_modelinfo import FieldModelInfo
from vsc2.impl.typeinfo import TypeInfo
from vsc2.impl.type_kind_e import TypeKindE


class FieldScalarImpl(FieldBaseImpl):
    
    def __init__(self, name, typeinfo, lib_field, is_signed):
        super().__init__(name, typeinfo, lib_field)
        
        self._is_signed = is_signed
        
    def get_val(self):
        if self._is_signed:
            return self._modelinfo._lib_obj.val().val_i()
        else:
            return self._modelinfo._lib_obj.val().val_u()
    
    def set_val(self, v):
        if self._is_signed:
            self._modelinfo._lib_obj.val().set_val_i(v)
        else:
            self._modelinfo._lib_obj.val().set_val_u(v)

    @property        
    def val(self):
        return self._modelinfo._lib_obj.val().val_i()

    @val.setter
    def val(self, v):
        self._modelinfo._lib_obj.val().set_val_i(v)
        

    
    def _bin_expr(self, op, rhs):
        ctor = Ctor.inst()
        
        print("_bin_expr: op=%s" % op, flush=True)

        if isinstance(rhs, Expr):
            rhs_e = rhs
        else:
            rhs_e = Expr.toExpr(rhs)
            
        ctor.pop_expr(rhs_e)

#        push_expr(ExprFieldRefModel(self._int_field_info.model))
        # Push a reference to this field
        lhs_e = Expr.toExpr(self)
        ctor.pop_expr(lhs_e)
        
        print("lhs_e=%s rhs_e=%s" % (str(lhs_e), str(rhs_e)), flush=True)

        if ctor.is_type_mode():
            model = ctor.ctxt().mkTypeExprBin(
                lhs_e._model, 
                op, 
                rhs_e._model)
        else:        
            model = ctor.ctxt().mkModelExprBin(
                lhs_e._model, 
                op, 
                rhs_e._model)
            
#        if in_srcinfo_mode():
#            e.srcinfo = SourceInfo.mk(2)
        
        return Expr(model)

    def __eq__(self, rhs):
        return self._bin_expr(core.BinOp.Eq, rhs)
    
    def __ne__(self, rhs):
        return self._bin_expr(core.BinOp.Ne, rhs)
    
    def __le__(self, rhs):
        return self._bin_expr(core.BinOp.Le, rhs)
    
    def __lt__(self, rhs):
        return self._bin_expr(core.BinOp.Lt, rhs)
    
    def __ge__(self, rhs):
        return self._bin_expr(core.BinOp.Ge, rhs)
    
    def __gt__(self, rhs):
        return self._bin_expr(core.BinOp.Gt, rhs)
    
    def __add__(self, rhs):
        return self._bin_expr(core.BinOp.Add, rhs)
    
    def __sub__(self, rhs):
        return self._bin_expr(core.BinOp.Sub, rhs)
    
    def __truediv__(self, rhs):
        return self._bin_expr(core.BinOp.Div, rhs)
    
    def __floordiv__(self, rhs):
        return self._bin_expr(core.BinOp.Div, rhs)
    
    def __mul__(self, rhs):
        return self._bin_expr(core.BinOp.Mul, rhs)
    
    def __mod__(self, rhs):
        return self._bin_expr(core.BinOp.Mod, rhs)
    
    def __and__(self, rhs):
        return self._bin_expr(core.BinOp.BinAnd, rhs)
    
    def __or__(self, rhs):
        return self._bin_expr(core.BinOp.BinOr, rhs)
    
    def __xor__(self, rhs):
        return self._bin_expr(core.BinOp.Xor, rhs)
    
    def __lshift__(self, rhs):
        return self._bin_expr(core.BinOp.Sll, rhs)
    
    def __rshift__(self, rhs):
        return self._bin_expr(core.BinOp.Srl, rhs)
    
    def __neg__(self):
        return self._bin_expr(core.BinOp.Not, rhs)
   
    def __invert__(self): 
        ctor = Ctor.inst()
        lhs = Expr.toExpr(self)
        ctor.pop_expr(lhs)

        if ctor.is_type_mode():
            raise Exception("mkTypeExprUnary not supported")
        else:
            return Expr(ctor.ctxt().mkExprModelUnary(core.UnaryOp.Not, lhs))
    
    def inside(self, rhs):
        self.to_expr()
        lhs_e = pop_expr()
        
        if isinstance(rhs, rangelist):
            return expr(ExprInModel(lhs_e, rhs.range_l))
        elif isinstance(rhs, rng):
            rl = ExprRangelistModel()
            rl.add_range(ExprRangeModel(rhs.low, rhs.high))
            return expr(ExprInModel(lhs_e, rl))
        elif isinstance(rhs, list_t):
            return expr(ExprInModel(
                lhs_e,
                ExprRangelistModel(
                    [ExprFieldRefModel(rhs.get_model())])))
        else:
            raise Exception("Unsupported 'inside' argument of type " + str(type(rhs)))

    def outside(self, rhs):
        self.not_inside(rhs)
            
    def not_inside(self, rhs):
        self.to_expr()
        lhs_e = pop_expr()
        
        if isinstance(rhs, rangelist):
            return expr(ExprUnaryModel(
                UnaryExprType.Not,
                ExprInModel(lhs_e, rhs.range_l)))
        elif isinstance(rhs, list_t):
            return expr(ExprUnaryModel(
                UnaryExprType.Not,
                ExprInModel(lhs_e,
                    ExprRangelistModel(
                        [ExprFieldRefModel(rhs.get_model())]))))
        else:
            raise Exception("Unsupported 'not_inside' argument of type " + str(type(rhs)) + " expect rangelist or list_t")
        
    
        
    def __getitem__(self, rng):
        ctor = Ctor.inst()
        
        if ctor.expr_mode():
            if isinstance(rng, slice):
                # slice
                upper = Expr.toExpr(rng.start)
                upper = ctor.pop_expr(upper)
                Expr.toExpr(rng.stop)
                lower = ctor.pop_expr()
                if ctor.is_type_mode():
                    raise Exception("mkTypeExprPartSelect not implemented")
                else:
                    return Expr(ctor.ctxt().mkModelExprPartSelect(
                        ctor.ctxt().mkModelExprFieldRefModel(self._modelinfo._lib_obj), 
                        upper, 
                        lower))
            else:
                # single value
                Expr.toExpr(rng)
                e = ctor.pop_expr()
                if ctor.is_type_mode():
                    raise Exception("mkTypeExprPartSelect not implemented")
                else:
                    return Expr(ctor.ctxt().mkModelExprPartSelect(
                        ctor.ctxt().mkModelExprFieldRef(self._modelinfo._lib_obj), e, e))
        else:
            curr = int(self.get_model().get_val())
            if isinstance(rng, slice):
                msk = ((1 << (rng.start-rng.stop+1))-1) << rng.stop
                curr = (curr & msk) >> rng.stop
            else:
                curr = (curr & (1 << rng)) >> rng
            return curr
            
    def __setitem__(self, rng, val):
        ctor = Ctor.inst()
        if not ctor.expr_mode():
            curr = int(self.get_model().get_val())
            if isinstance(rng, slice):
                msk = ((1 << (rng.start-rng.stop))-1) << rng.stop
                curr = (curr & msk) | (val << rng.stop & msk)
            else:
                curr = (curr & ~(val << rng)) | (val << rng)
            self.get_model().set_val(curr)
        else:
            raise Exception("Cannot assign to a part-select within a constraint")    


    