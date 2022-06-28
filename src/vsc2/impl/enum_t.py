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
    
    def __new__(cls, e_t, i=-1):
        ctor = Ctor.inst()

        print("e_t: %s" % str(e_t))        
        # Need to grab the enum type info
        info = EnumInfoMgr.inst().getInfo(e_t)
        
        lib_field = ctor.ctxt().mkModelFieldRoot(
            info.lib_obj,
            "")
        
        return FieldEnumImpl("", lib_field, info)
    pass