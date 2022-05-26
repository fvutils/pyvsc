'''
Created on May 25, 2022

@author: mballance
'''
from typing import Dict
from vsc2.impl.enum_info import EnumInfo

class EnumInfoMgr(object):
    
    _inst = None
    
    def __init__(self):
        self._enum_info_m = {}
        pass
    
    def getInfo(self, e_t):
        if e_t in self._enum_info_m.keys():
            return self._enum_info_m[e_t]
        else:
            info = EnumInfo(e_t)
            self._enum_info_m[e_t] = info
            return info
    
    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst
    
    