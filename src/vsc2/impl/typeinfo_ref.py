
from vsc2.impl.field_ref_impl import FieldRefImpl
from .typeinfo_vsc import TypeInfoVsc

class TypeInfoRef(TypeInfoVsc):
    
    def __init__(self):
        super().__init__(None, None)
    
    def createInst(
            self,
            modelinfo_p,
            name,
            idx):
        field = FieldRefImpl(name, idx)
        field._modelinfo.libobj = modelinfo_p.libobj.getField(idx)
        modelinfo_p.addSubfield(field._modelinfo)
        return field
