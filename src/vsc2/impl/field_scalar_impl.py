'''
Created on Mar 11, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from libvsc import core
from libvsc.core import Context
from vsc2.impl.expr import Expr
from vsc2.impl.field_modelinfo import FieldModelInfo

class FieldScalarImpl(object):
    
    def __init__(self, name, lib_field, iv=0):
        ctxt : Context = Ctor.inst().ctxt()
        self._modelinfo = FieldModelInfo(self, name)
        
        self._modelinfo._lib_obj = lib_field
        
        # if width <= 64:
        #     if is_signed:
        #         self._model.val().set_val_i(iv)
        #     else:
        #         self._model.val().set_val_u(iv)
        # else:
        #     raise Exception("Field >64 not supported")
        #
        # if is_rand:
        #     print("Set DeclRand")
        #     self._model.setFlag(core.ModelFieldFlag.DeclRand)
        #     self._model.setFlag(core.ModelFieldFlag.UsedRand)
        
    def model(self):
        return self._modelinfo._lib_obj
    
    def get_val(self):
        print("get_val: %d" % self._model.val().val_u())
        if self._is_signed:
            return self._model.val().val_i()
        else:
            return self._model.val().val_u()
    
    def set_val(self, v):
        if self._is_signed:
            self._model.val().set_val_i(v)
        else:
            self._model.val().set_val_u(v)

    @property        
    def val(self):
        return self._model.val().val_i()

    @val.setter
    def val(self, v):
        self._model.val().set_val_i(v)
        
    def _to_expr(self):
        ctor = Ctor.inst()

        if ctor.is_type_mode():
            ref = ctor.ctxt().mkTypeExprFieldRef()
            print("TODO: typemode")
            mi = self._modelinfo
            while mi._parent is not None:
                print("mi: %s" % str(mi))
                ref.addIdxRef(mi._idx)
                mi = mi._parent
            ref.addRootRef()
        else:        
            ref = ctor.ctxt().mkModelExprFieldRef(self.model())
        
        return Expr(ref)
    
    def _bin_expr(self, op, rhs):
        ctor = Ctor.inst()
        
        print("_bin_expr")

        if isinstance(rhs, Expr):        
            rhs_e = rhs
        else:
            rhs_e = Expr.toExpr(rhs)
            ctor.pop_expr()

#        push_expr(ExprFieldRefModel(self._int_field_info.model))
        # Push a reference to this field
        lhs_e = Expr.toExpr(self)
        ctor.pop_expr()

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
        return self._bin_expr(core.BinOp.And, rhs)
    
    def __or__(self, rhs):
        return self._bin_expr(core.BinOp.Or, rhs)
    
    def __xor__(self, rhs):
        return self._bin_expr(core.BinOp.Xor, rhs)
    
    def __lshift__(self, rhs):
        return self._bin_expr(core.BinOp.Sll, rhs)
    
    def __rshift__(self, rhs):
        return self._bin_expr(core.BinOp.Srl, rhs)
    
    def __neg__(self):
        return self._bin_expr(core.BinOp.Not, rhs)
   
    def __invert__(self): 
        self.to_expr()
        lhs = pop_expr()
        return expr(ExprUnaryModel(UnaryExprType.Not, lhs))
    
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
        if is_expr_mode():
            if isinstance(rng, slice):
                # slice
                to_expr(rng.start)
                upper = pop_expr()
                to_expr(rng.stop)
                lower = pop_expr()
                return expr(ExprPartselectModel(
                    ExprFieldRefModel(self._int_field_info.model), upper, lower))
            else:
                # single value
                to_expr(rng)
                e = pop_expr()
                return expr(ExprPartselectModel(
                    ExprFieldRefModel(self._int_field_info.model), e))
        else:
            curr = int(self.get_model().get_val())
            if isinstance(rng, slice):
                msk = ((1 << (rng.start-rng.stop+1))-1) << rng.stop
                curr = (curr & msk) >> rng.stop
            else:
                curr = (curr & (1 << rng)) >> rng
            return curr
            
    def __setitem__(self, rng, val):
        if not is_expr_mode():
            curr = int(self.get_model().get_val())
            if isinstance(rng, slice):
                msk = ((1 << (rng.start-rng.stop))-1) << rng.stop
                curr = (curr & msk) | (val << rng.stop & msk)
            else:
                curr = (curr & ~(val << rng)) | (val << rng)
            self.get_model().set_val(curr)
        else:
            raise Exception("Cannot assign to a part-select within a constraint")    


    