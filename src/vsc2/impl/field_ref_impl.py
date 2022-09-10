
from vsc2.impl.modelinfo import ModelInfo


class FieldRefImpl(object):

    def __init__(self, name, idx):
        self.target = None
        self._modelinfo = ModelInfo(self, name, None)
        self._modelinfo._idx = idx
        pass

    def get_val(self, modelinfo_p):
        print("get_val")
        this_f = modelinfo_p.libobj.getField(self._modelinfo._idx)
        print("this_f: %s" % str(this_f))
        target = this_f.getRef()

        if target is None:
            raise Exception("Attempting a null-reference dereference")
        
        return target.getFieldData()

    def set_val(self, lib_obj_p, val):
        print("FieldRefImpl.set_val")
        self.target = val
