'''
Created on Apr 7, 2022

@author: mballance
'''

from libvsc import core
from vsc2.impl.ctor import Ctor

class ModelInfo(object):
    
    def __init__(self, obj, name, typeinfo, idx=-1):
        self._obj = obj # User-facade object
        self._name = name
        self._typeinfo = typeinfo
        self._idx = idx
        self._libobj = None # Native object for the root of a data-structure tree
        self._parent = None
        self._randstate = None
        self._subfield_modelinfo = []
        self._is_topdown_scope = True
        self._is_ref = False

    @property
    def obj(self):
        return self._obj

    @obj.setter
    def obj(self, v):
        self._obj = v

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, v):
        self._name = v

    @property
    def idx(self):
        return self._idx

    @idx.setter
    def idx(self, v):
        self._idx = v

    @property
    def libobj(self):
        return self._libobj

    @libobj.setter
    def libobj(self, v):
        self._libobj = v
        
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
        
        
