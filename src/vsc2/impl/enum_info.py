'''
Created on May 25, 2022

@author: mballance
'''
from enum import EnumMeta

class EnumInfo(object):
    
    def __init__(self, e_t):
        self.e_t = e_t
        self.e2v_m = {}
        self.v2e_m = {}
        self.enums = []
       
        if isinstance(e_t, EnumMeta):
            i=0
            for en in e_t:
                # An IntEnum exposes its value via an __int__ method
                
                if hasattr(en, "__int__"):
                    i = int(en)
                self.e2v_m[en] = i
                self.v2e_m[i] = en
                self.enums.append(i)
                i += 1
        else:
            raise Exception("Unsupported enum type %s" % str(e_t))
        
        pass