'''
Created on Mar 11, 2022

@author: mballance
'''

class FieldScalarImpl(object):
    
    def __init__(self, width, is_signed, iv=0):
        pass
    
    def __get__(self, obj, objtype=None):
        print("__get__")
        return 20
    
    def __set__(self, obj, val):
        print("__set__")