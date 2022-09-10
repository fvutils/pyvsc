
from .ctor import Ctor
from .modelinfo import ModelInfo

class CompositeValClosure(object):

    def __init__(self, obj, modelinfo_p : ModelInfo):
        self.obj = obj
        self.modelinfo_p = modelinfo_p

    def __getattribute__(self, name: str):
        print("Closure::__getattribute__ %s" % name)
        ctor = Ctor.inst()
        ret = object.__getattribute__(obj, name)

        if not ctor.raw_mode():
            ctor.push_raw_mode()
            if ctor.expr_mode():
                pass
            elif hasattr(ret, "get_val"):
                print("Closure:: replacing with get_val")
                ret = ret.get_val(self.modelinfo_p)
            ctor.pop_raw_mode()

        return ret

    # def __setattr__(self, name, value):
    #     print("CompositeValueClosure::__setattr__ %s %s" % (name, str(value)))
    # # def __setattr__(self, name: str, value):
    # #     print("CompositeValueClosure::__setattr__ %s" % name)
    # #     try:
    # #         obj = object.__getattribute__(self, "obj")
    # #     except:
    # #         object.__setattr__(self, name, value)
    # #     else:
    # #         try:
    # #             fo = object.__getattribute__(obj, name)
    # #         except:
    # #             object.__setattr__(obj, name, value)
    # #         else:
    # #             modelinfo_p = object.__getattribute__(self, "modelinfo_p")
    # #             if hasattr(fo, "set_val"):
    # #             fo.set_val(self.modelinfo_p, value)
