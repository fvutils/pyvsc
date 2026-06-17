'''
Created on Oct 12, 2021

@author: mballance
'''
import random

class RandState(object):
        
    def __init__(self, seed):
        # Seed via the constructor so the Mersenne Twister is initialized once
        # (string seed), not twice — `random.Random()` first seeds from OS
        # entropy, and a following `.seed(...)` throws that away. Passing the
        # seed to the constructor produces the identical value stream at ~half
        # the cost; this is on the per-instance randomize() hot path.
        self.rng = random.Random(f"{seed}")
    
    def clone(self) -> 'RandState':
        randState = RandState("")
        randState.rng.setstate(self.rng.getstate())
        return randState 
    
    def rand_u(self):
        val = self.rng.randint(0, 0xFFFFFFFFFFFFFFFF)
        return val
    
    def rand_s(self):
        val = self.rand_u()
        
        if (val&(1 << 63)) != 0:
            # Negative number
            val = -((~val & 0xFFFFFFFFFFFFFFFF)+1)
            
        return val
    
    def randint(self, low, high) -> int:
        low = int(low)
        high = int(high)
        
        if high < low:
            tmp = low
            low = high
            high = tmp
        
        val = self.rng.randint(low, high)
        return val
    
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