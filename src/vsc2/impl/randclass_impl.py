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

class RandClassImpl(object):
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        Tp = dataclasses.dataclass(T, init=False)
        
        Tp._field_ctor_m = {}

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

                if f.name not in Tp._field_ctor_m.keys():
                    if f.default is not _MISSING_TYPE:
                        iv = f.default
                    else:
                        iv = 0
#                    setattr(Tp, f.name, property(FieldScalarImpl.__get__, FieldScalarImpl.__set__))
#                    setattr(Tp, f.name, FieldScalarDesc())
                    print("Register with is_rand=%d" % is_rand)
                    Tp._field_ctor_m[f.name] = lambda t=t,r=is_rand,i=iv: RandClassImpl.__create(t, r, i)
                # TODO: fill in factory
            else:
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

    @staticmethod    
    def __create(t, is_rand, iv):
        ret = t.create(iv)
        ret.is_rand = is_rand
        print("__create: %d" % is_rand)
        return ret
    
    #****************************************************************
    #* Implementation methods for user objects
    #****************************************************************
    
    def __init(self, base, *args, **kwargs):
        # TODO: Push a context into which to add fields
        
        Ctor.inst()
        
        base(self, *args, *kwargs)
        print("_randclass __init__")

        print("_field_ctor_m: %s" % str(self._field_ctor_m))
        for name,ctor in self._field_ctor_m.items():
            f = ctor()
            setattr(self, name, f)

        # TODO: determine if we're at leaf level (?)        
        pass
    
    def __randomize(self):
        pass
    
    def __setattr(self, name, v):
        try:
            fo = object.__getattribute__(self, name)
        except:
            object.__setattr__(self, name, v)
        else:
            object.__setattr__(self, name, v)
        
    def __getattr(self, name):
        ret = object.__getattribute__(self, name)
        
        # TODO: Check whether this is a 'special' field
        
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

