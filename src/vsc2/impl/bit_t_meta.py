'''
Created on Feb 26, 2022

@author: mballance
'''
from vsc2.impl.scalar_t import ScalarT


class BitTMeta(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("bit_t[%d]" % item, (ScalarT,), {})
            t.W = item
            t.S = False
            return t
        