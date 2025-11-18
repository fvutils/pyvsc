'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.value import Value, ValueType
from vsc.model.value_bool import ValueBool

class ValueInt(int):
    """Wrapper for 'int' values. Permits operators"""
    
    @classmethod
    def from_bits(cls, value, width, signed=False):
        """
        Create a ValueInt from a bit pattern with specified width and signedness.
        
        Args:
            value: The bit pattern value (integer)
            width: The bit width (e.g., 8, 16, 32)
            signed: Whether to interpret the value as signed (default: False)
            
        Returns:
            ValueInt: A properly interpreted integer value
            
        Example:
            >>> ValueInt.from_bits(0xFF, 8, signed=True)  # Returns -1
            >>> ValueInt.from_bits(0xFF, 8, signed=False) # Returns 255
        """
        # Mask to the specified width
        mask = (1 << width) - 1
        masked_value = int(value) & mask
        
        # If signed and MSB is set, convert to negative (two's complement)
        if signed and (masked_value & (1 << (width - 1))):
            # Convert to negative: -(2^width - value)
            result = -((1 << width) - masked_value)
        else:
            result = masked_value
            
        return cls(result)
     
    def __getitem__(self, rng):
        val =  self.__int__()
        
        if isinstance(rng, slice):
            if (rng.start < rng.stop):
                raise Exception("integer slice bounds are reversed. Expect [%d:%d]" % (
                    rng.stop, rng.start))
            mask = ((1 << ((rng.start-rng.stop)+1)) - 1)
            return ((val >> rng.stop) & mask)
        else:
            # Single bit
            return ((val >> rng) & 1)

class ValueScalar(Value):
    
    def __init__(self, v : int):
        super().__init__(ValueType.Scalar)
        self.v = v
        
    def toString(self):
        return str(self.v)
    
    @property
    def val(self):
        return self.v
    
    def __int__(self):
        return ValueInt(self.v)
    
    def toInt(self):
        return ValueInt(self.v)
    
    def __bool__(self):
        return self.v != 0
    
    def __eq__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v == v)
    
    def __ne__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v != v)
    
    def __gt__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v > v)
    
    def __ge__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v >= v)
    
    def __lt__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v < v)
    
    def __le__(self, rhs):
        v = int(rhs)
        return ValueBool(self.v <= v)
    
    def __add__(self, rhs):
        v = int(rhs)
        return ValueScalar(self.v + v)
    
    def __and__(self, rhs):
        v = int(rhs)
        return ValueScalar(self.v & v)
    
    def __sub__(self, rhs):
        v = int(rhs)
        return ValueScalar(self.v - v)
    
    def __getitem__(self, rng):
        print("getitem")

