'''
Created on Apr 6, 2022

@author: mballance
'''

class TypeInfo(object):
    
    def __init__(self, kind, lib_typeobj):
        self._kind = kind
        self._lib_typeobj = lib_typeobj