'''
Created on Mar 11, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from libvsc.core import Context

class FieldScalarImpl(object):
    
    def __init__(self, name, width, is_signed, is_rand, iv=0):
        ctxt : Context = Ctor.inst().ctxt()
        self._model = ctxt.mkModelFieldRoot(
            ctxt.mkDataTypeInt(is_signed, width),
            name)
        
        if width <= 64:
            if is_signed:
                self._model.val().set_val_i(iv)
            else:
                self._model.val().set_val_u(iv)
        else:
            raise Exception("Field >64 not supported")
        
    def model(self):
        return self._model

    @property        
    def val(self):
        return self._model.val().val_i()

    @val.setter
    def val(self, v):
        self._model.val().set_val_i(v)
    