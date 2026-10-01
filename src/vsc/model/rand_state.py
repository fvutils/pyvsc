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

    def draw(self, low, high):
        """Uniform inclusive draw over [low, high] -- same distribution as
        ``randint``, ~4x faster.

        ``Random.randint`` routes through ``randrange``, whose argument
        validation dominates at these rates: 0.21 us vs 0.05 us measured, which
        on a 128-element array draw is 27 us of a 43 us loop. This is the
        rejection method ``Random`` itself uses underneath, called directly.

        Used by the direct-draw path (unconstrained + T0 fields) only; the
        solver back-ends keep ``randint`` so their seeded streams are untouched.
        """
        n = high - low + 1
        if n <= 1:
            # n == 1 is the common point-domain case. n < 1 is a caller bug
            # (hi < lo); return the endpoint rather than spin forever in the
            # rejection loop below.
            return low
        getrandbits = self.rng.getrandbits
        k = (n - 1).bit_length()
        v = getrandbits(k)
        while v >= n:
            v = getrandbits(k)
        return low + v

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