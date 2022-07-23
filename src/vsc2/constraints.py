'''
Created on Apr 16, 2022

@author: mballance
'''

import libvsc.core as core
from .impl.ctor import Ctor
from .impl.expr import Expr

#********************************************************************
#* if/then constraints
#********************************************************************

class if_then(object):

    def __init__(self, e):
        ctor = Ctor.inst()

        if not ctor.in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        cond_e = Expr.toExpr(e)
        ctor.pop_expr(cond_e)

        if ctor.is_type_mode():
            true_c = ctor.ctxt().mkTypeConstraintScope()
            self.stmt = ctor.ctxt().mkTypeConstraintIfElse(
                cond_e.model,
                true_c,
                None)
        else:
            true_c = ctor.ctxt().mkModelConstraintScope()
            self.stmt = ctor.ctxt().mkModelConstraintIfElse(
                cond_e.model,
                true_c,
                None)

#        if in_srcinfo_mode():
#            self.stmt.srcinfo = SourceInfo.mk()
        ctor.push_constraint_scope(true_c)
        
    def __enter__(self):
        pass
        
    def __exit__(self, t, v, tb):
        ctor = Ctor.inst()
        ctor.pop_constraint_scope()
        ctor.constraint_scope().addConstraint(self.stmt)

class else_if(object):

    def __init__(self, e):
        self.stmt = None
        ctor = Ctor.inst()
        
        if not ctor.in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        last_stmt = ctor.last_constraint_stmt()
        if last_stmt == None or not isinstance(last_stmt, (core.ModelConstraintIfElse,core.TypeConstraintIfElse)):
            raise Exception("Attempting to use else_if where it doesn't follow if_then")
        
        cond_e = Expr.toExpr(e)
        ctor.pop_expr(cond_e)

        # Need to find where to think this in
        while last_stmt.getFalse() is not None:
            last_stmt = last_stmt.getFalse()

        if ctor.is_type_mode():            
            raise Exception("TODO")
        else:
            self.stmt = ctor.ctxt().mkModelConstraintIfElse(
                cond_e._model,
                None,
                None)

#        if in_srcinfo_mode():
#            self.stmt.srcinfo = SourceInfo.mk()
        last_stmt.false_c = self.stmt
        
    def __enter__(self):
        if self.stmt is not None:
            self.stmt.true_c = ConstraintScopeModel()
            push_constraint_scope(self.stmt.true_c)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()

class else_then_c(object):

    def __init__(self):
        pass
    
    def __call__(self):
        return self
        
    def __enter__(self):
        ctor = Ctor.inst()
        if not ctor.in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        last_stmt = ctor.last_constraint_stmt()
        print("last_stmt=%s" % str(last_stmt))
        if last_stmt is None or not isinstance(last_stmt, (core.ModelConstraintIfElse,core.TypeConstraintIfElse)):
            raise Exception("Attempting to use else_then where it doesn't follow if_then/else_if")
        
        # Need to find where to think this in
        while last_stmt.getFalse() is not None:
            last_stmt = last_stmt.getFalse()

        if ctor.is_type_mode():            
            stmt = ctor.ctxt().mkTypeConstraintScope()
        else:
            stmt = ctor.ctxt().mkModelConstraintScope()
        last_stmt.setFalse(stmt)
        ctor.push_constraint_scope(stmt)
        
    def __exit__(self, t, v, tb):
        ctor = Ctor.inst()
        ctor.pop_constraint_scope()

else_then = else_then_c()


def soft(e):
    ctor = Ctor.inst()

    if not ctor.in_constraint_scope():
       raise Exception("Attempting to use soft constraint outside constraint scope")

    e_expr = Expr.toExpr(e)
    ctor.pop_expr(e_expr)

    if ctor.is_type_mode():
        c = ctor.ctxt().mkTypeConstraintSoft(
            ctor.ctxt().mkTypeConstraintExpr(e_expr._model))
    else:
        c = ctor.ctxt().mkModelConstraintSoft(
            ctor.ctxt().mkModelConstraintExpr(e_expr._model))
    
    ctor.constraint_scope().addConstraint(c)

def unique(*args):
    ctor = Ctor.inst()

    expr_l = []
    for i in range(-1,-(len(args)+1), -1):
        expr_e = Expr.toExpr(args[i])
        ctor.pop_expr(expr_e)
        expr_l.append(expr_e._model)
    
    if ctor.is_type_mode():
        c = ctor.ctxt().mkTypeConstraintUnique(expr_l)
    else:
        c = ctor.ctxt().mkModelConstraintUnique(expr_l)
    
    ctor.constraint_scope().addConstraint(c)


