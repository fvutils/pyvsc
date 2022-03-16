'''
Created on Feb 26, 2022

@author: mballance
'''
from vsc2.impl.field_scalar_impl import FieldScalarImpl

class ScalarT(FieldScalarImpl):
    W = 0
    S = False
    
    def __init__(self, name="", iv=0):
        super().__init__(name, type(self).W, type(self).S, False, iv)

    @classmethod
    def createField(cls, name, is_rand, iv):
        print("ScalarT::create %d %d iv=%s" % (cls.W, cls.S, str(iv)))
        ret = FieldScalarImpl(name, cls.W, cls.S, is_rand, iv)
        return ret
    