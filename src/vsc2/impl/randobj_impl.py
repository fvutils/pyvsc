#****************************************************************************
#* Created on Feb 26, 2022
#*
#* @author: mballance
#****************************************************************************
import dataclasses
from vsc2.impl.scalar_t import ScalarT
from vsc2.types import rand

class RandObjImpl(object):
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        Tp = dataclasses.dataclass(T, init=False)
        
        for f in dataclasses.fields(Tp):
            print("Field: %s" % str(f)) 
            
            if issubclass(f.type, rand):
                print("isrand")
                t = f.type.__args__[0]
                print(f.type.__args__)
            else:
                t = f.type
            
            if issubclass(t, ScalarT):
                print("   Is a scalar: %d,%d" % (t.W, t.S))
                # TODO: fill in factory
            else:
#                print("   Is a scalar: %d,%d" % (f.type.W, f.type.S))
                pass
            
        base_init = Tp.__init__
        Tp.__init__ = lambda self, *args, **kwargs: RandObjImpl.__init(
            self, base_init, *args, *kwargs)
        Tp.randomize = lambda self: RandObjImpl.__randomize(self)
        Tp.randomize_with = lambda self: RandObjImpl.__randomize_with(self)
        return Tp
    
    #****************************************************************
    #* Implementation methods for user objects
    #****************************************************************
    
    def __init(self, base, *args, **kwargs):
        base(self, *args, *kwargs)
        print("_randobj_init")
        pass
    
    def __randomize(self):
        pass
    
    def __randomize_with(self):
        pass
