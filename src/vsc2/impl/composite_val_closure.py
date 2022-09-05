
from .ctor import Ctor
from .field_modelinfo import FieldModelInfo

class CompositeValClosure(object):

    def __init__(self, obj, modelinfo_p : FieldModelInfo):
        self.obj = obj
        self.modelinfo_p = modelinfo_p

    def __getattribute__(self, name: str):
        ctor = Ctor.inst()
        ret = object.__getattribute__(self.obj, name)

        if ctor.expr_mode():
            pass
        elif hasattr(ret, "get_val"):
            ret = ret.get_val(self.modelinfo_p)

        return ret
