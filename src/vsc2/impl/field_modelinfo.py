'''
Created on Apr 7, 2022

@author: mballance
'''

class FieldModelInfo(object):
    
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name
        self._lib_obj = None
        self._idx = -1
        self._parent = None
        
    @property
    def parent(self):
        return self._parent
    
    @parent.setter
    def parent(self, p):
        self._parent = p
        
