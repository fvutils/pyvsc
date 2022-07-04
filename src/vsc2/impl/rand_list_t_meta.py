'''
Created on Jun 28, 2022

@author: mballance
'''
from vsc2.impl.list_t import ListT
from vsc2.impl.rand_t import RandT


class RandListTMeta(type):
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("list_t[%s]" % str(item), (ListT,), {})
            t.T = item
            tr = type("rand_t[%s]" % str(t), (RandT,), {})
            tr.T = t
            
            self.type_m[item] = tr
            return tr