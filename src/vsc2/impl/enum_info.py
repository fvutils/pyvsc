'''
Created on May 25, 2022

@author: mballance
'''
from enum import EnumMeta
from vsc2.impl.ctor import Ctor

class EnumInfo(object):
    
    def __init__(self, e_t):
        self.e_t = e_t
        self.e2v_m = {}
        self.v2e_m = {}
        self.enums = []
        
        ctor = Ctor.inst()

        have_neg = False
        max_width = 8
        
        # Take a pre-processing step to determine
        # - What is the max width of enumerator?
        # - Are there any negative elements?
        if isinstance(e_t, EnumMeta):
            i=0
            for en in e_t:
                # An IntEnum exposes its value via an __int__ method
                
                if hasattr(en, "__int__"):
                    i = int(en)
                if i < 0:
                    have_neg = True
                    
                ai = abs(i)
                for w in [8, 16, 24, 32, 64]:
                    if ai <= ((1 << w) - 1):
                        if w > max_width:
                            max_width = w
                        break
                i += 1
        else:
            raise Exception("Unsupported enum type %s" % str(e_t))
        
        self.lib_obj = ctor.ctxt().findDataTypeEnum(e_t.__qualname__)
        
        if self.lib_obj is not None:
            raise Exception("Duplicate enum %s" % e_t.__qualname__)
        
        self.lib_obj = ctor.ctxt().mkDataTypeEnum(e_t.__qualname__, have_neg)
        val = ctor.ctxt().mkModelVal()
        val.setBits(max_width)
       
        if isinstance(e_t, EnumMeta):
            i=0
            for en in e_t:
                # An IntEnum exposes its value via an __int__ method
                
                if hasattr(en, "__int__"):
                    i = int(en)
                val.set_val_u(i)
                self.lib_obj.addEnumerator(en.name, val)
                self.e2v_m[en] = i
                self.v2e_m[i] = en
                self.enums.append(i)
                i += 1
        else:
            raise Exception("Unsupported enum type %s" % str(e_t))
        
        ctor.ctxt().addDataTypeEnum(self.lib_obj)
        
        pass