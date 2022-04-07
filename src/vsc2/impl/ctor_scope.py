'''
Created on Mar 14, 2022

@author: mballance
'''

class CtorScope(object):
    
    def __init__(self, facade_obj, lib_scope, type_mode):
        self._facade_obj = facade_obj
        self._lib_scope = lib_scope
        self._type_mode = type_mode
        self._inh_depth = 1
        self._field_idx = 0

    @property        
    def facade_obj(self):
        return self._facade_obj

    @facade_obj.setter    
    def facade_obj(self, obj):
        self._facade_obj = obj

    @property    
    def lib_scope(self):
        return self._lib_scope
    
    def inh_depth(self):
        return self._inh_depth
     
    def inc_inh_depth(self):
        self._inh_depth += 1
        return self._inh_depth
        
    def dec_inh_depth(self):
        self._inh_depth -= 1
        return self._inh_depth

    def next_field_idx(self):
        ret = self._field_idx
        self._field_idx += 1
        return ret
