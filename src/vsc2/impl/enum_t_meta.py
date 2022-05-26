'''
Created on Feb 27, 2022

@author: mballance
'''
from vsc2.impl.enum_t import EnumT
from vsc2.impl.enum_info_mgr import EnumInfoMgr

class EnumTMeta(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("enum_t[%s]" % item.__qualname__, (EnumT,), {})
            t.EnumInfo = EnumInfoMgr.inst().getInfo(item)
            self.type_m[item] = t
            return t
    
