'''
Created on Feb 26, 2022

@author: mballance
'''
from vsc2.impl.field_scalar_impl import FieldScalarImpl

class ScalarT(object):
    W = 0
    S = False
    
    def __init__(self):
        raise Exception("Standalone creation of fields is not supported")
    
    
    
    @classmethod
    def create(cls, iv):
        print("ScalarT::create %d %d" % (cls.W, cls.S))
        ret = FieldScalarImpl(cls.W, cls.S, iv)
        return ret
    