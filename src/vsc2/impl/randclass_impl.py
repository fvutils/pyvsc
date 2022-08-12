'''
Created on Apr 6, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from libvsc import core
from vsc2.impl import field_scalar_impl
from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.field_modelinfo import FieldModelInfo


class RandClassImpl(object):
    """Implementation methods for @randclass-decorated classes"""

    @staticmethod
    def init(self, base, *args, **kwargs):
        # TODO: Push a context into which to add fields
        ctor = Ctor.inst()
        typeinfo = type(self)._typeinfo

        s = ctor.scope()

        if s is not None:
            if s.facade_obj is None:
                # The field-based caller has setup a frame for us. 
                # Add the object reference
                s.facade_obj = self
            elif s.facade_obj is self:
                s.inc_inh_depth()
            else:
                # Need a new scope
                if s._type_mode:
                    raise Exception("Shouldn't hit this in type mode")
                print("TODO: Create root field for %s" % type(self)._typeinfo._lib_typeobj.name())
                self._model = ctor.ctxt().buildModelField(typeinfo._lib_typeobj, "<>")
                self._randstate = ctor.ctxt().mkRandState(0)
                s = ctor.push_scope(self, self._model, False)
        else:
            # Push a new scope. Know we're in non-type mode
            print("TODO: Create root field for %s" % type(self)._typeinfo._lib_typeobj.name())
            self._model = ctor.ctxt().buildModelField(typeinfo._lib_typeobj, "<>")
            self._randstate = ctor.ctxt().mkRandState("0")
            s = ctor.push_scope(self, self._model, False)
            
        self._modelinfo = FieldModelInfo(self, "<>", typeinfo)
        self._modelinfo._lib_obj = s._lib_scope
        
        base(self, *args, *kwargs)
        print("_randclass __init__")

        print("_field_ctor_m: %s" % str(self._typeinfo._field_typeinfo))
        for field_ti in self._typeinfo._field_typeinfo:
            print("name: %s" % field_ti._name)

            # What to pass here?
            
                    # Grab the appropriate field from the scope
            field = s.lib_scope.getField(field_ti._idx)
            
            f = field_ti._ctor(
                field,
                field_ti._name,
                field_ti._idx)
            f._modelinfo.parent = self._modelinfo
            setattr(self, field_ti._name, f)
            
#            s.lib_scope.addField(f.model())

        # TODO: determine if we're at leaf level (?)
        if s.dec_inh_depth() == 0 and ctor.is_type_mode():
            # Time to pop this level. But before we do so, build
            # out the relevant constraints
            print("TODO: build out constraints: %s" % str(typeinfo._constraint_m))

            ctor.push_expr_mode()
            for c in self._typeinfo._constraint_l:
                cb = ctor.ctxt().mkTypeConstraintBlock(c._name)
                ctor.push_constraint_scope(cb)
                print("--> Invoke constraint")
                c._method_t(self)
                print("<-- Invoke constraint")
                ctor.pop_constraint_scope()
                
                self._modelinfo._lib_obj.addConstraint(cb)
            ctor.pop_expr_mode()
            
            ctor.pop_scope()
        pass
    
    @staticmethod
    def setattr(self, name, v):
        try:
            fo = object.__getattribute__(self, name)
        except:
            object.__setattr__(self, name, v)
        else:
            object.__setattr__(self, name, v)
            
    @staticmethod
    def getattr(self, name):
        ctor = Ctor.inst()
        ret = object.__getattribute__(self, name)

        if not ctor.expr_mode():
            # TODO: Check whether this is a 'special' field
            if hasattr(ret, "get_val"):
                ret = ret.get_val()
        
        return ret

    @staticmethod
    def randomize(self, debug=0, lint=0, solve_fail_debug=0):
        ctxt = Ctor.inst().ctxt()

        solver = ctxt.mkCompoundSolver()
        
        if debug > 0:
            pass

        print("--> solver.solve", flush=True)        
        solver.solve(
            self._randstate,
            [self._model],
            [],
            core.SolveFlags.Randomize+core.SolveFlags.RandomizeDeclRand+core.SolveFlags.RandomizeTopFields
            )
        print("<-- solver.solve", flush=True)        
        
        if debug > 0:
            pass

    class RandomizeWithClosure(object):
        
        def __init__(self, obj):
            self._obj = obj
        
        def __enter__(self):
            return self._obj
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    @classmethod                
    def randomize_with(cls, self):
        return cls.RandomizeWithClosure(self)
        pass
    
    @staticmethod    
    def createPrimField(lib_field, name, idx, is_signed):
        typeinfo = None
        ctor = Ctor.inst()
        print("__createPrimField %s" % name)

        field = FieldScalarImpl(name, typeinfo, lib_field, is_signed)
        field._modelinfo._idx = idx
        
        
        print("  field=%s" % str(lib_field))
        
#        ret = field_scalar_impl()
#        ret = t.createField(name, is_rand, iv)
#        print("__create: %d" % is_rand)
        return field

        