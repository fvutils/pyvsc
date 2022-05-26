'''
Created on Mar 20, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from libvsc import core

class Expr(object):
    
    def __init__(self, model):
        self._model = model
        Ctor.inst().push_expr(self)
        
    @staticmethod
    def toExpr(rhs):
        if isinstance(rhs, Expr):
            return rhs
        elif hasattr(rhs, "_to_expr"):
            return rhs._to_expr()
        elif type(rhs) == int:
            ctor = Ctor.inst()
           
            if ctor.is_type_mode():
                ev = Ctor.inst().ctxt().mkTypeExprVal(None)
            else:
                ev = Ctor.inst().ctxt().mkModelExprVal(None)
            ev.val().setBits(64)
            ev.val().set_val_i(rhs)
            return Expr(ev)
        else:
            raise Exception("toExpr failed")
        
    def _bin_expr(self, op, rhs):
        ctor = Ctor.inst()
        ctxt = ctor.ctxt()
        
        rhs_e = Expr.toExpr(rhs)
        lhs_e = self._model

        ctor.pop_expr(rhs)
        ctor.pop_expr()
       
        model = ctxt.mkModelExprBin(
            lhs_e, 
            op, 
            rhs_e)
        
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
    
    # TODO: is this needed?    
    def __call__(self, T):
        return T    
    
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
        lhs = pop_expr()
        
        return expr(ExprUnaryModel(UnaryExprType.Not, lhs))
    
    def inside(self, rhs):
        lhs_e = pop_expr()
        
        if isinstance(rhs, rangelist):
            return expr(ExprInModel(lhs_e, rhs.range_l))
        elif isinstance(rhs, list_t):
            return expr(ExprInModel(
                lhs_e,
                ExprRangelistModel(
                    [ExprFieldRefModel(rhs.get_model())])))
        else:
            raise Exception("Unsupported 'inside' argument of type " + str(type(rhs)) + 
                            "expect vsc.rangelist or list_t")

    def outside(self, rhs):
        self.not_inside(rhs)
            
    def not_inside(self, rhs):
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
            raise Exception("Unsupported 'not_inside' argument of type " + str(type(rhs)))
        
    def __getitem__(self, k):
        if is_expr_mode():
            if isinstance(k, slice):
                # Part-select on a field expression
                print("k=" + str(k) + " start=" + str(k.start) + " stop=" + str(k.stop))
                
                to_expr(k.start)
                upper = pop_expr()
                to_expr(k.stop)
                lower = pop_expr()
                
                base_e = pop_expr()
                return expr(ExprPartselectModel(base_e, upper, lower))
            else:
                # single value
                to_expr(k)
                idx_e = pop_expr()
                base_e = pop_expr()
                
                return expr_subscript(ExprArraySubscriptModel(
                    base_e,
                    idx_e))
        else:
            raise Exception("Calling __getitem__ on an expr on non-expression context")    