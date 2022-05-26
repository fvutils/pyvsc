'''
Created on Feb 27, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from vsc2.impl.field_enum_impl import FieldEnumImpl
from vsc2.impl.enum_info_mgr import EnumInfoMgr


class EnumT(object):

    # Holds enum info in the case that a type declaration
    # was created
    EnumInfo = None
    
    def __new__(cls, e_t):
        ctor = Ctor.inst()
        
        # Need to grab the enum type info
        info = EnumInfoMgr.inst().getInfo(e_t)
        
        
        print("e_t: %s" % e_t.__qualname__)

        return FieldEnumImpl()
        pass
    pass