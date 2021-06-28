'''
Created on May 16, 2020

@author: ballance
'''
from vsc.model.value import Value, ValueType
from vsc.model.value_bool import ValueBool

# class ValueInt(int):
#     
#     def __getitem__(self, rng):
#         val =  str.__int__()
#         if 
#         print("int rng: " + str(self.__int__()))
#         for v in dir(self):
#             print("  v: " + str(v))

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
    
#    def toInt(self):
#        return ValueInt(self.v)
    
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
    
    def __sub__(self, rhs):
        v = int(rhs)
        return ValueScalar(self.v - v)
    
    def __getitem__(self, rng):
        print("getitem")

