'''
Created on Apr 6, 2022

@author: mballance
'''

import typeworks
from vsc2.impl.composite_val_closure import CompositeValClosure
from vsc2.impl.ctor import Ctor
from libvsc import core
from .rand_state import RandState
from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.modelinfo import ModelInfo
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
        object.__setattr__(self, name, v)
        # ctor = Ctor.inst()

        # if ctor.raw_mode():
        #     object.__setattr__(self, name, v)
        # else:
        #     print("SETATTR: %s %s" % (name, str(v)), flush=True)
        #     try:
        #         fo = object.__getattribute__(self, name)
        #     except:
        #         object.__setattr__(self, name, v)
        #     else:
        #         if hasattr(fo, "set_val"):
        #             fo.set_val(self._modelinfo._lib_obj, v)
        #         else:
        #             object.__setattr__(self, name, v)
            
    @staticmethod
    def __getattribute__(self, name):
        ctor = Ctor.inst()
        ret = object.__getattribute__(self, name)

        if not ctor.raw_mode() and not name.startswith("__"):
            ctor.push_raw_mode()
            if ctor.expr_mode() or ctor.is_type_mode():
                # TODO: should transform into an expression proxy
                # TODO: must handle type mode
                pass
            elif hasattr(ret, "get_val"):
                # Value mode. 
                # The target is a vsc field. Calling get_val() either
                # returns the field value (ie if the field is a scalar),
                # or returns a closure that can be further queried
                # if the field is a composite
                ret = ret.get_val(self._modelinfo)
            ctor.pop_raw_mode()
        return ret

    @staticmethod
    def get_val(self, modelinfo_p : ModelInfo):
        # Obtain the appropriate field-info from the parent
        print("RandClass::get_val")
        return CompositeValClosure(
            self,
            modelinfo_p._subfield_modelinfo[self._modelinfo._idx]
        )
    
    @staticmethod
    def randomize(self, debug=0, lint=0, solve_fail_debug=0):
        modelinfo : ModelInfo = self._modelinfo
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

    @classmethod
    def addMethods(cls, T):
        T.__init__ = cls.init
        T.randomize = cls.randomize
        T.randomize_with = cls.randomize_with
        T.__setattr__ = cls.setattr
        T.__getattribute__ = cls.__getattribute__
#        T.get_val = cls.get_val

        
