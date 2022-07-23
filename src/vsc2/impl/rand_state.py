
import random
from .ctor import Ctor

class RandState(object):

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
    def mk(cls):
        """Creates a random-state object using the Python random state"""
        seed = random.randint(0, 0xFFFFFFFF)
        return RandState(f"{seed}")
   
    @classmethod
    def mkFromSeed(cls, seed, strval=None):
        """Creates a random-state object from a numeric seed and optional string"""
        if strval is not None:
            seed = f"{seed} : {strval}"
        return RandState(seed)    
