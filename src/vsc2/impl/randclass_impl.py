#****************************************************************************
#* Created on Feb 26, 2022
#*
#* @author: mballance
#****************************************************************************
from dataclasses import _MISSING_TYPE
import dataclasses

from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.scalar_t import ScalarT
from vsc2.types import rand
import libvsc
from vsc2.impl.ctor import Ctor
from vsc2.impl.randclass_typeinfo import RandClassTypeInfo
from vsc2.impl import ctor

class RandClassImpl(object):
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        Tp = dataclasses.dataclass(T, init=False)

        print("RandClass %s" % str(T))
        Tp._is_randclass = True
        Tp._typeinfo = RandClassTypeInfo()
        
        print("  Bases: %s" % str(T.__bases__))
        
        constraints = Ctor.inst().pop_constraint_decl()
        Tp._typeinfo._constraint_l.extend(constraints)
        
        for c in constraints:
            Tp._typeinfo._constraint_m[c._name] = c
            
        for b in T.__bases__:
            if hasattr(b, "_typeinfo"):
                self.__collectConstraints(Tp._typeinfo, b)
            
        # Process dataclass fields to determine which 
        # require special treatment because they are 
        # PyVSC fields        
        for f in dataclasses.fields(Tp):
            print("==> Field: %s" % str(f)) 

            is_rand = False
            if issubclass(f.type, rand):
                print("isrand")
                t = f.type.__args__[0]
                print(f.type.__args__)
                is_rand = True
            else:
                t = f.type
            
            if issubclass(t, ScalarT):
                print("   Is a scalar: %d,%d" % (t.W, t.S))

                if f.name not in Tp._typeinfo._field_ctor_m.keys():
                    if not isinstance(f.default, dataclasses._MISSING_TYPE):
                        iv = f.default
                        if type(iv) != int:
                            raise Exception("Initial value for field %s (%s) is not integral" % (f.name, str(iv)))
                    else:
                        iv = 0
                        
                        
#                    setattr(Tp, f.name, property(FieldScalarImpl.__get__, FieldScalarImpl.__set__))
#                    setattr(Tp, f.name, FieldScalarDesc())
                    print("Register with is_rand=%d" % is_rand)
                    Tp._typeinfo._field_ctor_m[f.name] = lambda t=t,n=f.name,r=is_rand,i=iv: RandClassImpl.__createPrimField(t, n, r, i)
                # TODO: fill in factory
            else:
                raise Exception("Non-scalar fields are not yet supported")
#                print("   Is a scalar: %d,%d" % (f.type.W, f.type.S))
                pass
            
            print("<== Field: %s" % str(f)) 
            
        base_init = Tp.__init__
        Tp.__init__ = lambda self, *args, **kwargs: RandClassImpl.__init(
            self, base_init, *args, *kwargs)
        Tp.randomize = lambda self: RandClassImpl.__randomize(self)
        Tp.randomize_with = lambda self: RandClassImpl.__randomize_with(self)
        Tp.__setattr__ = lambda self, name, val: RandClassImpl.__setattr(self, name, val)
        Tp.__getattribute__ = lambda self, name: RandClassImpl.__getattr(self, name)
        return Tp
    
    def __collectConstraints(self, typeinfo, clsT):
        """Connect constraints from base classes"""
        # First, connect any additional constraints registered in the base class
        for cn,cd in clsT._typeinfo._constraint_m.items():
            if cn not in typeinfo._constraint_m.keys():
                print("Adding base-class %s" % cn)
                typeinfo._constraint_l.append(cd)
                typeinfo._constraint_m[cn] = cd
            else:
                print("Skipping overridden %s" % cn)
                pass
                
        # Now, keep digging
        for b in clsT.__bases__:
            if hasattr(b, "_typeinfo"):
                self.__collectConstraints(typeinfo, b)


    @staticmethod    
    def __createPrimField(t, name, is_rand, iv):
        ret = t.createField(name, is_rand, iv)
        print("__create: %d" % is_rand)
        return ret
    
    #****************************************************************
    #* Implementation methods for user objects
    #****************************************************************
    
    def __init(self, base, *args, **kwargs):
        # TODO: Push a context into which to add fields
        typeinfo = type(self)._typeinfo
        ctor = Ctor.inst()
        s = ctor.scope()
        
        if s is not None:
            if s.obj is None:
                # The field-based caller has setup a frame for us. 
                # Add the object reference
                s.obj = self
            elif s.obj() == self:
                s.inc_inh_depth()
            else:
                # Need a new scope
                self._model = ctor.ctxt().mkModelFieldRoot(None, "<>")
                s = ctor.push_scope(self, self._model)
        else:
            # Push a new scope
            self._model = ctor.ctxt().mkModelFieldRoot(None, "<>")
            s = ctor.push_scope(self, self._model)
        
        base(self, *args, *kwargs)
        print("_randclass __init__")

        print("_field_ctor_m: %s" % str(self._typeinfo._field_ctor_m))
        for name,ctor_f in self._typeinfo._field_ctor_m.items():
            f = ctor_f()
            setattr(self, name, f)
            
            s.field().addField(f.model())

        # TODO: determine if we're at leaf level (?)
        if s.dec_inh_depth() == 0:
            # Time to pop this level. But before we do so, build
            # out the relevant constraints
            print("TODO: build out constraints: %s" % str(typeinfo._constraint_m))

            ctor.push_expr_mode()
            for c in self._typeinfo._constraint_l:
                cb = ctor.ctxt().mkModelConstraintBlock(c._name)
                ctor.push_constraint_scope(cb)
                print("--> Invoke constraint")
                c._method_t(self)
                print("<-- Invoke constraint")
                ctor.pop_constraint_scope()
                
                self._model.addConstraint(cb)
            ctor.pop_expr_mode()
            
            ctor.pop_scope()
        
        pass
    
    def __randomize(self):
        ctxt = Ctor.inst().ctxt()

        randstate = ctxt.mkRandState(0)
        randomizer = ctxt.mkRandomizer(None, randstate)

        print("--> randomize", flush=True)        
        randomizer.randomize(
            [self._model],
            [],
            False)
        print("<-- randomize", flush=True)        
        
        pass
    
    def __setattr(self, name, v):
        try:
            fo = object.__getattribute__(self, name)
        except:
            object.__setattr__(self, name, v)
        else:
            object.__setattr__(self, name, v)
        
    def __getattr(self, name):
        ctor = Ctor.inst()
        ret = object.__getattribute__(self, name)

        if not Ctor.inst().expr_mode():
            # TODO: Check whether this is a 'special' field
            if hasattr(ret, "get_val"):
                ret = ret.get_val()
        
        return ret
    
    class RandomizeWithClosure(object):
        
        def __init__(self, obj):
            self._obj = obj
        
        def __enter__(self):
            return self._obj
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    
    def __randomize_with(self):
        return RandClassImpl.RandomizeWithClosure(self)

