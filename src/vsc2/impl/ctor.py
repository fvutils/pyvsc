'''
Created on Mar 11, 2022

@author: mballance
'''
from libvsc import core
from vsc2.impl.ctor_scope import CtorScope

class Ctor():
    
    _inst = None
    
    def __init__(self):
        self._ctxt = core.Context.inst()
        
        print("Ctor: ctxt=%s" % str(self._ctxt))
        self._scope_s = []
        self._constraint_l = []
        self._constraint_s = []
        self._expr_s = []
        self._expr_mode_s = []
        pass
    
    def ctxt(self):
        return self._ctxt
    
    def scope(self):
        if len(self._scope_s) > 0:
            return self._scope_s[-1]
        else:
            return None
        
    def push_scope(self, facade_obj, lib_scope, type_mode):
        s = CtorScope(facade_obj, lib_scope, type_mode)
        self._scope_s.append(s)
        return s
        
    def pop_scope(self):
        self._scope_s.pop()
        
    def is_type_mode(self):
        return len(self._scope_s) > 0 and self._scope_s[-1]._type_mode
        
    def push_expr(self, e):
        self._expr_s.append(e)
        
    def pop_expr(self):
        self._expr_s.pop()
        
    def expr(self):
        if len(self._expr_s) > 0:
            return self._expr_s[-1]
        else:
            return None
        
    def push_expr_mode(self, m=True):
        self._expr_mode_s.append(m)
        
    def expr_mode(self):
        return len(self._expr_mode_s) > 0 and self._expr_mode_s[-1]
        
    def pop_expr_mode(self):
        return self._expr_mode_s.pop()
        
    def push_constraint_decl(self, c):
        self._constraint_l.append(c)
        
    def pop_constraint_decl(self):
        ret = self._constraint_l.copy()
        self._constraint_l.clear()
        return ret
    
    def push_constraint_scope(self, c):
        self._constraint_s.append(c)
        
    def constraint_scope(self):
        return self._constraint_s[-1]
    
    def pop_constraint_scope(self):
        # Collect remaining expressions and convert to expr_statements
        cb = self._constraint_s.pop()
        
        for e in self._expr_s:
            if self.is_type_mode():
                c = self.ctxt().mkTypeConstraintExpr(e._model)
            else:
                c = self.ctxt().mkModelConstraintExpr(e._model)
            cb.addConstraint(c)
        self._expr_s.clear()
            
        return cb
    
    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = Ctor()
        return cls._inst
        