'''
Created on Feb 26, 2022

@author: mballance
'''
from vsc2.impl.scalar_t import ScalarT


class IntTMeta(type):
    """Meta-class for int_t types. Generates a unique int_t for each unique width"""
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("int_t[%d]" % item, (ScalarT,), {})
            t.W = item
            t.S = True
            return t
        