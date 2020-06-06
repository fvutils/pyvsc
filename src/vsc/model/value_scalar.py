'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.value import Value, ValueType
from vsc.model.value_bool import ValueBool

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
        return self.v
    
    def __bool__(self):
        return self.v != 0
    
    def __eq__(self, rhs):
        return ValueBool(self.v == rhs.v)
    
    def __ne__(self, rhs):
        return ValueBool(self.v != rhs.v)
    
    def __gt__(self, rhs):
        return ValueBool(self.v > rhs.v)
    
    def __ge__(self, rhs):
        return ValueBool(self.v >= rhs.v)
    
    def __lt__(self, rhs):
        return ValueBool(self.v < rhs.v)
    
    def __le__(self, rhs):
        return ValueBool(self.v <= rhs.v)
    
    def __add__(self, rhs):
        return ValueScalar(self.v + rhs.v)
    
    def __sub__(self, rhs):
        return ValueScalar(self.v - rhs.v)
