'''
Created on Jun 29, 2022

@author: mballance
'''
from vsc2.impl.expr import Expr
from vsc2.impl.ctor import Ctor

class rng(object):
    
    def __init__(self, low, high):
        ctor = Ctor.inst()
        
        self.low = Expr.toExpr(low)
        ctor.pop_expr(self.low)
       
        self.high = Expr.toExpr(high)
        ctor.pop_expr(self.high) 
        
class rangelist(object):
    
    def __init__(self, *args):
        if len(args) == 0:
            raise Exception("Empty rangelist specified")
        
        ctor = Ctor.inst()

        if ctor.is_type_mode():
            self.range_l = ctor.ctxt().mkTypeExprRangelist()
        else:
            self.range_l = ctor.ctxt().mkModelExprRangelist()

        for i in range(-1,-(len(args)+1), -1):
            a = args[i]
            if isinstance(a, tuple):
                # This needs to be a two-element array
                if len(a) != 2:
                    raise Exception("Range specified with " + str(len(a)) + " elements is invalid. Two elements required")
                e0 = Expr.toExpr(a[0])
                ctor.pop_expr(e0)
                e1 = Expr.toExpr(a[1])
                ctor.pop_expr(e1)
                if ctor.is_type_mode():
                    self.range_l.addRange(ctor.ctxt().mkTypeExprRange(
                        False, e0._model, e1._model))
                else:
                    self.range_l.addRange(ctor.ctxt().mkModelExprRange(
                        False, e0._model, e1._model))
            elif isinstance(a, rng):
                if ctor.is_type_mode():
                    self.range_l.addRange(ctor.ctxt().mkTypeExprRange(
                        False, a.low._model, a.high._model))
                else:
                    self.range_l.addRange(ctor.ctxt().mkModelExprRange(
                        False, a.low._model, a.high._model))
            elif isinstance(a, list):
                for ai in a:
                    to_expr(ai)
                    eai = pop_expr()
                    self.range_l.addRange(eai)
            else:
                to_expr(a)
                e = pop_expr()
                self.range_l.addRange(e)
#            self.range_l.rl.reverse()

                # This needs to be convertioble to a
                
    def clear(self):
        self.range_l.rl.clear()
                
    def extend(self, ranges):
        for a in ranges:
            self.append(a)

    def append(self, a):
        if isinstance(a, tuple):
            # This needs to be a two-element array
            if len(a) != 2:
                raise Exception("Range specified with " + str(len(a)) + " elements is invalid. Two elements required")
            to_expr(a[0])
            e0 = pop_expr()
            to_expr(a[1])
            e1 = pop_expr()
            self.range_l.add_range(ExprRangeModel(e0, e1))
        elif isinstance(a, rng):
            self.range_l.add_range(ExprRangeModel(a.low, a.high))
        elif isinstance(a, list):
            for ai in a:
                to_expr(ai)
                eai = pop_expr()
                self.range_l.add_range(eai)
        else:
            to_expr(a)
            e = pop_expr()
            self.range_l.add_range(e)        
                
    def __contains__(self, lhs):
        ctor = Ctor.inst()
        lhs_e = Expr.toExpr(lhs)
        ctor.pop_expr(lhs_e)

        if ctor.is_type_mode():
            raise Exception("ExprIn")
        else:
            # Really need a 'clone' method
            return Expr(ctor.ctxt().mkModelExprIn(lhs_e._model, self.range_l))
    
    def __invert__(self):
        print("rangelist.__invert__")
        