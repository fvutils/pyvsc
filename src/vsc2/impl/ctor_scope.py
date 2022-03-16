'''
Created on Mar 14, 2022

@author: mballance
'''

class CtorScope(object):
    
    def __init__(self, obj, field):
        self._obj = obj
        self._field = field
        self._inh_depth = 1

    @property        
    def obj(self):
        return self._obj

    @obj.setter    
    def set_obj(self, obj):
        self._obj = obj
    
    def field(self):
        return self._field
   
    def inh_depth(self):
        return self._inh_depth
     
    def inc_inh_depth(self):
        self._inh_depth += 1
        return self._inh_depth
        
    def dec_inh_depth(self):
        self._inh_depth -= 1
        return self._inh_depth

