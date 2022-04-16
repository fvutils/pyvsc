'''
Created on Mar 18, 2022

@author: mballance
'''

class ConstraintDecl(object):
    """Holds information about a specific constraint declaration"""
    
    def __init__(self, name, method_t):
        self._name = name
        self._method_t = method_t
        
    @property
    def name(self):
        return self._name
    
    def __call__(self, obj):
        self._method_t(obj)
        
    pass