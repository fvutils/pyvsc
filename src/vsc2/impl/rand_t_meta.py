'''
Created on Apr 15, 2022

@author: mballance
'''
from vsc2.impl.rand_t import RandT

class RandTMeta(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type('rand_t[%s]' % str(item), (RandT,), {})
            t.T = item
            self.type_m[item] = t
            return t
        