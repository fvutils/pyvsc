'''
Created on Apr 6, 2022

@author: mballance
'''
from enum import Enum, auto

class TypeKindE(Enum):
    Field = auto()
    Enum = auto()
    List = auto()
    Scalar = auto()
    RandClass = auto()
    RandObj = auto()
    