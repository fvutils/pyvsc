'''
Created on Jun 28, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from vsc2.impl.field_list_impl import FieldListImpl
from vsc2.impl.scalar_t import ScalarT
from vsc2.impl.enum_t import EnumT
import typing

class ListT(object):
    T = None
    
    def __new__(cls,
                t,
                sz=0,
                is_rand=False,
                is_randsz=False,
                init=None):
        ctor = Ctor.inst()

        lib_type = None
        if hasattr(t, "_modelinfo"):
            print("Is instance -- no type")
            
        elif hasattr(t, "_typeinfo"):
            print("Is user-defined type")
            
        print("type(t)=%s" % str(type(t)))

        # if True:
        #     if issubclass(t, ScalarT):
        #         print("Scalar")
        #     elif issubclass(t, EnumT):
        #         print("Enum")
        #     elif hasattr(t, "_typeinfo"):
        #         print("User-defined type")
        #     else:
        #         raise Exception("Type \"%s\" is not a recognized VSC type" % str(type(t)))
        # else:
        #     print("non-type class")

        
        lib_field = ctor.ctxt().mkModelFieldVecRoot(
            lib_type,
            "")
        
        ret = FieldListImpl("", lib_field)
        
        return ret
    