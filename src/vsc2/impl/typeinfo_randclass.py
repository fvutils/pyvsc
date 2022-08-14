'''
Created on Mar 18, 2022

@author: mballance
'''
from typing import List

from .field_modelinfo import FieldModelInfo

from .ctor import Ctor

from .typeinfo_field import TypeInfoField
from .constraint_decl import ConstraintDecl
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo_vsc import TypeInfoVsc

class TypeInfoRandClass(TypeInfoVsc):
    
    def __init__(self, info, kind=TypeKindE.RandClass):
        super().__init__(info, kind)
        self._field_ctor_m = {}
        self._constraint_m = {}
        self._constraint_l = []
        self._field_typeinfo = []
        self._base_init = None
        
    def init(self, obj, args, kwargs):
        # Run the base behavior
        self._info.init(obj, args, kwargs)
        
        # TODO: Push a context into which to add fields
        ctor = Ctor.inst()

        s = ctor.scope()

        if s is not None:
            if s.facade_obj is None:
                # The field-based caller has setup a frame for us. 
                # Add the object reference
                s.facade_obj = obj
            elif s.facade_obj is obj:
                s.inc_inh_depth()
            else:
                # Need a new scope
                if s._type_mode:
                    raise Exception("Shouldn't hit this in type mode")
                print("TODO: Create root field for %s" % self.lib_typeobj.name())
                obj._model = ctor.ctxt().buildModelField(self.lib_typeobj, "<>")
                obj._randstate = ctor.ctxt().mkRandState("0")
                s = ctor.push_scope(obj, obj._model, False)
        else:
            # Push a new scope. Know we're in non-type mode
            print("Self: %s" % str(self), flush=True)
            print("TODO: Create root field for %s" % self.lib_typeobj.name())
            obj._model = ctor.ctxt().buildModelField(self.lib_typeobj, "<>")
            obj._randstate = ctor.ctxt().mkRandState("0")
            s = ctor.push_scope(obj, obj._model, False)
            
        obj._modelinfo = FieldModelInfo(self, "<>", self)
        obj._modelinfo._lib_obj = s._lib_scope
        
        for field_ti in self.getFields():
            print("name: %s" % field_ti.name)

            # What to pass here?
            
                    # Grab the appropriate field from the scope
            field = s.lib_scope.getField(field_ti._idx)
            
            f = field_ti._ctor(
                field,
                field_ti._name,
                field_ti._idx)
            obj._modelinfo.addSubfield(f._modelinfo)
            setattr(obj, field_ti._name, f)
            
#            s.lib_scope.addField(f.model())

        # TODO: determine if we're at leaf level (?)
        if s.dec_inh_depth() == 0 and ctor.is_type_mode():
            # Time to pop this level. But before we do so, build
            # out the relevant constraints
            print("TODO: build out constraints: %s" % str(self.getConstraints()))

            # This doesn't seem right...
            ctor.push_expr_mode()
            for c in self.getConstraints():
                cb = ctor.ctxt().mkTypeConstraintBlock(c._name)
                ctor.push_constraint_scope(cb)
                print("--> Invoke constraint")
                c._method_t(obj)
                print("<-- Invoke constraint")
                ctor.pop_constraint_scope()
                
                obj._modelinfo._lib_obj.addConstraint(cb)
            ctor.pop_expr_mode()
            ctor.pop_scope()        

    def addField(self, field_ti):
        self._lib_typeobj.addField(field_ti._lib_typeobj)
        self._field_typeinfo.append(field_ti)
        
    def getFields(self) -> List[TypeInfoField]:
        return self._field_typeinfo
        
    def addConstraint(self, c : ConstraintDecl):
        self._constraint_m[c.name] = c
        self._constraint_l.append(c)
        
    def addConstraints(self, c_l : List[ConstraintDecl]):
        for c in c_l:
            self.addConstraint(c)
            
    def getConstraints(self) -> List[ConstraintDecl]:
        return self._constraint_l
        
    @staticmethod
    def get(info) -> 'TypeInfoRandClass':
        if not hasattr(info, TypeInfoVsc.ATTR_NAME):
            setattr(info, TypeInfoVsc.ATTR_NAME, TypeInfoRandClass(info))
        return getattr(info, TypeInfoVsc.ATTR_NAME)

