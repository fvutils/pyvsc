'''
Created on Jun 28, 2022

@author: mballance
'''
from vsc2.impl.list_t import ListT

class ListTMeta(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("list_t[%s]" % str(item), (ListT,), {})
            t.T = item
            self.type_m[item] = t
            return t
        
    