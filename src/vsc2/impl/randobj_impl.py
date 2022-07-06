'''
Created on May 22, 2022

@author: mballance
'''
from vsc2.impl import ctor
from vsc2.impl.ctor import Ctor
from libvsc import core
from vsc2.impl.field_modelinfo import FieldModelInfo
from vsc1.model.field_model import FieldModel
from vsc2.impl.type_kind_e import TypeKindE

class RandObjImpl(object):

    @staticmethod    
    def init(self, base, *args, **kwargs):
        ctor = Ctor.inst()
        
        s = ctor.scope()

        if s is not None:
            if s.facade_obj is None:
                s.facade_obj = self
            elif s.facade_obj is self:
                s.inc_inh_depth()
            else:
                # Need a new scope for this field
                self._model = ctor.ctxt().mkModelFieldRoot(None, "<>")
                self._randstate = ctor.ctxt().mkRandState(0)
                s = ctor.push_scope(self, self._model, False)
        else: # s is None
            self._model = ctor.ctxt().mkModelFieldRoot(None, "<>")
            self._randstate = ctor.ctxt().mkRandState(0)
            s = ctor.push_scope(self, self._model, False)

        print("init: %d" % s.inh_depth())
        
        if s.inh_depth() == 1:
            self._modelinfo = FieldModelInfo(
                self, 
                "<>",
                type(self)._typeinfo)
            self._modelinfo._lib_obj = s._lib_scope
        
        base(self, *args, *kwargs)

        # Time 
        if s.dec_inh_depth() == 0:
            
            # Collect and connect VSC fields to the
            # broader data model
            Ctor.inst().push_expr_mode()
            for fn in dir(self):
                fo = getattr(self, fn)
                if hasattr(fo, "_modelinfo"):
                    print("fn: %s" % fn)
                    mi : FieldModelInfo = fo._modelinfo
                    mi._lib_obj.setName(fn)
                    s.lib_scope.addField(mi._lib_obj)
                    
            # Build out constraints
            for c in type(self)._typeinfo._constraint_l:
                cb = ctor.ctxt().mkModelConstraintBlock(c._name)
                print("--> constraint")
                ctor.push_constraint_scope(cb)
                c._method_t(self)
                print("<-- constraint")
                ctor.pop_constraint_scope()
                self._modelinfo._lib_obj.addConstraint(cb)
            
            Ctor.inst().pop_expr_mode()
        
            # TODO: Collect and build out constraints
            ctor.pop_scope()

    @staticmethod    
    def __getattribute__(self, attr):
        ctor = Ctor.inst()
        
        ret = object.__getattribute__(self, attr)
        
        if not ctor.expr_mode():
            if hasattr(ret, "get_val"):
                ret = ret.get_val()
                
        return ret
    
    @staticmethod
    def __setattr__(self, attr, val):
        try:
            fo = object.__getattribute__(self, attr)
        except:
            object.__setattr__(self, attr, val)
        else:
            if hasattr(fo, "_modelinfo"):
                # We're not in expression context, so the user 
                # really wants us to say the actual value of
                # the field.
                if hasattr(val, "_modelinfo"):
                    ctor = Ctor.inst()
                    # Looks like we're re-assigning it
                    if ctor.scope() is not None and ctor.scope().inh_depth() > 0:
                        object.__setattr__(self, attr, val)
                    else:
                        raise Exception("Cannot re-construct field")
                elif hasattr(fo, "set_val"):
                    fo.set_val(val)
                else:
                    object.__setattr__(self, attr, val)
            else:
                object.__setattr__(self, attr, val)
            
        pass
    
    
    @staticmethod
    def randomize(self, **kwargs):
        # TODO: solve options
        
        ctxt = Ctor.inst().ctxt()
        
        solver = ctxt.mkCompoundSolver()
        
        solver.solve(
            self._randstate,
            [self._model],
            [],
            core.SolveFlags.Randomize+
                core.SolveFlags.RandomizeDeclRand+
                core.SolveFlags.RandomizeTopFields)
        pass
    
    class RandWithClosure(object):
        
        def __init__(self, obj):
            self._obj = obj
        
        def __enter__(self):
            ctor = Ctor.inst()
            cs = ctor.ctxt().mkModelConstraintBlock("xx")
            ctor.push_constraint_scope(cs)
            ctor.push_expr_mode()
            return self._obj
    
        def __exit__(self, t, v, tb):
            ctor = Ctor.inst()
            ctor.pop_expr_mode()
            cs = ctor.pop_constraint_scope()
            mi = self._obj._modelinfo
            
            if mi._randstate is None:
                mi._randstate = ctor.ctxt().mkRandState(0)
            
            solver = ctor.ctxt().mkCompoundSolver()
            
            print("Solve: lib_obj=%s" % str(mi._lib_obj), flush=True)
        
            solver.solve(
                mi._randstate,
                [mi._lib_obj],
                [cs],
                core.SolveFlags.Randomize+
                    core.SolveFlags.RandomizeDeclRand+
                    core.SolveFlags.RandomizeTopFields)
    
    @staticmethod
    def randomize_with(self, **kwargs):
        print("self=%s" % str(self))
        return RandObjImpl.RandWithClosure(self)
        pass
    
    @staticmethod
    def set_randstate(self, state):
        pass

    @staticmethod
    def get_randstate(self):
        pass

    
    @classmethod
    def addMethods(cls, T):
        base = T.__init__
        setattr(T, "__init__", lambda self, *args, **kwargs: RandObjImpl.init(self, base, *args, *kwargs))
        setattr(T, "__getattribute__", cls.__getattribute__)
        setattr(T, "__setattr__", cls.__setattr__)
        setattr(T, "randomize", cls.randomize)
        setattr(T, "randomize_with", cls.randomize_with)
        setattr(T, "set_randstate", cls.set_randstate)
        setattr(T, "get_randstate", cls.get_randstate)
    
    pass