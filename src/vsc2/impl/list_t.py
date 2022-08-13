'''
Created on Jun 28, 2022

@author: mballance
'''
import typing

from vsc2.impl.ctor import Ctor
from vsc2.impl.enum_t import EnumT
from vsc2.impl.field_list_object_impl import FieldListObjectImpl
from vsc2.impl.field_list_scalar_impl import FieldListScalarImpl
from vsc2.impl.scalar_t import ScalarT
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo_vsc import TypeInfoVsc


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
        typeinfo = None
        kind = None
        if hasattr(t, "_modelinfo"):
            print("Is instance -- no type")
            typeinfo = t._modelinfo._typeinfo
            kind = t._modelinfo._typeinfo._kind
            lib_type = t._modelinfo._typeinfo._lib_typeobj
        elif hasattr(t, "_typeinfo"):
            print("Is user-defined type")
            
        print("kind: %s" % kind)

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
        
        if kind == TypeKindE.Scalar:
            ret = FieldListScalarImpl(
                "", 
                TypeInfoVsc(TypeKindE.List, None, typeinfo),
                lib_field)
        elif kind == TypeKindE.Enum:
            pass
        elif kind == TypeKindE.RandObj:
            ret = FieldListObjectImpl(
                "", 
                TypeInfoVsc(TypeKindE.List, None, typeinfo),
                lib_field)
        
        
        return ret
    