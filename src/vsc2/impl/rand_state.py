
import random
import libvsc.core as vsc_core
from .ctor import Ctor

class RandState(object):

    _glblState : vsc_core.RandState = None

    def __init__(self, seed : str):
        ctor = Ctor.inst()
        self._model = ctor.ctxt().mkRandState(f"{seed}")
    
    def clone(self) -> 'RandState':
        ret = RandState()
        ret._model = self._model.clone()
        return ret

    def setState(self, state):
        self._model.setState(state._model)
    
    def rand_u(self):
        return self._model.rand_ui64()
    
    def rand_s(self):
        return self._model.rand_i64()
    
    def randint(self, low, high):
        return self._model.randint32(low, high)

    @classmethod
    def seed(cls, seed : str):
        ctor = Ctor.inst()
        cls._glblState = ctor.ctxt().mkRandState(f"{seed}")
        pass
    
    @classmethod
    def mk(cls):
        """Creates a random-state object using the Python random state"""
        if cls._glblState is None:
            ctor = Ctor.inst()
            cls._glblState = ctor.ctxt().mkRandState("0")
        seed = cls._glblState.randint32(0, 0x7FFFFFFF)
        print("seed=%d" % seed)
        return RandState(f"{seed}")
   
    @classmethod
    def mkFromSeed(cls, seed, strval=None):
        """Creates a random-state object from a numeric seed and optional string"""
        if strval is not None:
            seed = f"{seed} : {strval}"
        return RandState(seed)    
