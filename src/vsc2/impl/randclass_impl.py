'''
Created on Apr 6, 2022

@author: mballance
'''

import typeworks
from vsc2.impl.ctor import Ctor
from libvsc import core
from .rand_state import RandState
from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.field_modelinfo import FieldModelInfo
from .typeinfo_randclass import TypeInfoRandClass


class RandClassImpl(object):
    """Implementation methods for @randclass-decorated classes"""

    @staticmethod
    def init(self, *args, **kwargs):
        randclass_ti = TypeInfoRandClass.get(typeworks.TypeInfo.get(type(self)))
        randclass_ti.init(self, args, kwargs)
        

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
        modelinfo : FieldModelInfo = self._modelinfo
        ctxt = Ctor.inst().ctxt()

        if self._randstate is None:
            self._randstate = RandState.mk()

        modelinfo.pre_randomize()
        
        solver = ctxt.mkCompoundSolver()
        
        if debug > 0:
            pass

        solver.solve(
            self._randstate,
            [self._model],
            [],
            core.SolveFlags.Randomize+core.SolveFlags.RandomizeDeclRand+core.SolveFlags.RandomizeTopFields
            )
        
        modelinfo.post_randomize()
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
        print("__createPrimField %s" % name, flush=True)

        field = FieldScalarImpl(name, typeinfo, lib_field, is_signed)
        field._modelinfo._idx = idx
        
        
        print("  field=%s" % str(lib_field))
        
#        ret = field_scalar_impl()
#        ret = t.createField(name, is_rand, iv)
#        print("__create: %d" % is_rand)
        return field

        
