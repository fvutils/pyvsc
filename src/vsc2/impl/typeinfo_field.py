'''
Created on Apr 6, 2022

@author: mballance
'''
from vsc2.impl.typeinfo_vsc import TypeInfoVsc
from vsc2.impl.type_kind_e import TypeKindE

class TypeInfoField(object):
    
    def __init__(self, name, typeinfo):
        self.name = name
        self.typeinfo = typeinfo
        self.idx = -1

    def createInst(
        self,
        modelinfo_p,
        name,
        idx):
        print("TypeInfoField.createInst: %s" % name)
        return self.typeinfo.createInst(modelinfo_p, name, idx)

