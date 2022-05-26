'''
Created on May 25, 2022

@author: mballance
'''

from libvsc.core import Context

from vsc2.impl.ctor import Ctor
from vsc2.impl.expr import Expr
from vsc2.impl.field_modelinfo import FieldModelInfo


class FieldBaseImpl(object):
    
    def __init__(self, name, lib_field):
        ctxt : Context = Ctor.inst().ctxt()
        self._modelinfo = FieldModelInfo(self, name)
        self._modelinfo._lib_obj = lib_field
        
    def model(self):
        return self._modelinfo._lib_obj
    
    def _to_expr(self):
        ctor = Ctor.inst()

        if ctor.is_type_mode():
            ref = ctor.ctxt().mkTypeExprFieldRef()
            mi = self._modelinfo
            while mi._parent is not None:
                ref.addIdxRef(mi._idx)
                mi = mi._parent
            ref.addRootRef()
        else:        
            print("FieldScalarImpl._to_expr (%s)" % self.model().name(), flush=True)
            ref = ctor.ctxt().mkModelExprFieldRef(self.model())
        
        return Expr(ref)
    