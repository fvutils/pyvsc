'''
Created on Apr 7, 2022

@author: mballance
'''

from libvsc import core

class FieldModelInfo(object):
    
    def __init__(self, obj, name, typeinfo):
        self._obj = obj
        self._name = name
        self._typeinfo = typeinfo
        self._lib_obj = None
        self._idx = -1
        self._parent = None
        self._randstate = None
        self._subfield_modelinfo = []
        
    @property
    def parent(self):
        return self._parent
    
    @parent.setter
    def parent(self, p):
        self._parent = p
        
    def addSubfield(self, subfield_mi):
        subfield_mi.parent = self
        self._subfield_modelinfo.append(subfield_mi)
        
    def pre_randomize(self):
        if hasattr(self._obj, "pre_randomize"):
            self._obj.pre_randomize()
        for field_mi in self._subfield_modelinfo:
            field_mi.pre_randomize()
            
    def post_randomize(self):
        if hasattr(self._obj, "post_randomize"):
            self._obj.post_randomize()
        for field_mi in self._subfield_modelinfo:
            field_mi.post_randomize()
        
    def set_rand(self):
        self._lib_obj.setFlag(core.ModelFieldFlag.DeclRand)
        
        
