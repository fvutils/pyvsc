'''
Created on Mar 18, 2022

@author: mballance
'''

class ConstraintDecl(object):
    """Holds information about a specific constraint declaration"""
    
    def __init__(self, name, method_t):
        self._name = name
        self._method_t = method_t
        
    pass