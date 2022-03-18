'''
Created on Mar 11, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
import libvsc.core as core
from libvsc.core import Context

class FieldScalarImpl(object):
    
    def __init__(self, name, width, is_signed, is_rand, iv=0):
        ctxt : Context = Ctor.inst().ctxt()
        self._is_signed = is_signed
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
        
        if is_rand:
            print("Set DeclRand")
            self._model.setFlag(core.ModelFieldFlag.DeclRand)
            self._model.setFlag(core.ModelFieldFlag.UsedRand)
        
    def model(self):
        return self._model
    
    def get_val(self):
        if self._is_signed:
            return self._model.val().val_i()
        else:
            return self._model.val().val_u()
    
    def set_val(self, v):
        if self._is_signed:
            self._model.val().set_val_i(v)
        else:
            self._model.val().set_val_u(v)

    @property        
    def val(self):
        return self._model.val().val_i()

    @val.setter
    def val(self, v):
        self._model.val().set_val_i(v)
    