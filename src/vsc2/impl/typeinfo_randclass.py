'''
Created on Mar 18, 2022

@author: mballance
'''
from typing import List
import libvsc.core as libvsc

from rctgen.impl.modelinfo_component import ModelInfoComponent

from .modelinfo import ModelInfo

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
        
    def init(self, 
        obj, 
        args, 
        kwargs,
        modelinfo=None,
        ctxt_b=None):
        # Run the base behavior
        self._info.init(obj, args, kwargs)
        
        # TODO: Push a context into which to add fields
        ctor = Ctor.inst()

        if ctxt_b is None:
            ctxt_b = libvsc.ModelBuildContext(ctor.ctxt())

        if modelinfo is None:
            modelinfo = ModelInfoComponent(obj, "<>", self)

        s = ctor.scope()

        print("s=%s" % str(s))

        ctor.push_raw_mode()

        # Create modelinfo for this field
        obj._modelinfo = modelinfo

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
                obj._modelinfo.libobj = self.lib_typeobj.mkRootField(ctxt_b, "<>", False)
                obj._randstate = None
                s = ctor.push_scope(obj, obj._modelinfo.libobj, False)
        else:
            # Push a new scope. Know we're in non-type mode
            print("Self: %s" % str(self), flush=True)
            print("TODO: Create root field for %s" % self.lib_typeobj.name())
            obj._modelinfo.libobj = self.lib_typeobj.mkRootField(ctxt_b, "<>", False)
            obj._randstate = None
            s = ctor.push_scope(obj, obj._modelinfo.libobj, False)

        # Capture the active composite-type scope
        modelinfo.libobj = s.lib_scope

        if not ctor.is_type_mode():
            print("Set Data: %08x" % id(obj))
            if s.lib_scope is not None:
                s.lib_scope.setFieldData(obj)
        
        for field_ti in self.getFields():
            print("name: %s" % field_ti.name)

            # What to pass here?
            
            # Grab the appropriate field from the scope
            print("lib_scope=%s" % str(s.lib_scope), flush=True)

            # Field constructor responsible for adding itself
            # to the parent modelinfo
            print("field_ti.idx: %d ; getField: %s" % (field_ti.idx, str(s.lib_scope.getField(field_ti.idx))))
#            ctor.push_scope(None, s.lib_scope.getField(field_ti.idx), ctor.is_type_mode())
            f = field_ti.createInst(
                modelinfo,
                field_ti.name,
                field_ti.idx)
#            ctor.pop_scope()

            print("Set Attr: %s=%s" % (field_ti.name, str(f)))
            setattr(obj, field_ti.name, f)
            
#            s.lib_scope.addField(f.model())

        ctor.pop_raw_mode()

        # TODO: determine if we're at leaf level (?)
        if s.dec_inh_depth() == 0:
            if ctor.is_type_mode():
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

    def createInst(
            self,
            modelinfo_p,
            name,
            idx):
        field = self.info.Tp()
        # Back-patch name and index -- something not available inside the constructor
        field._modelinfo.name = name
        field._modelinfo.idx = idx
        modelinfo_p.addSubfield(field._modelinfo)

        return field

    def createTypeInst(self):
        ctor = Ctor.inst()

        ctor.push_scope(None, self.lib_typeobj, True)
        obj = self.info.Tp()

        return obj

    def elab(self, obj):
        self.elabConstraints(obj)

    def elabConstraints(self, obj):
        """
        Elaborate constraint types
        """
        ctor = Ctor.inst()

        ctor.push_scope(obj, self.lib_typeobj, True)
        ctor.push_expr_mode()        
        for c in self.getConstraints():
            cs = ctor.ctxt().mkTypeConstraintBlock(c.name)
            ctor.push_constraint_scope(cs)
            c(obj)
            ctor.pop_constraint_scope()
            self.lib_typeobj.addConstraint(cs)
        ctor.pop_expr_mode()
        ctor.pop_scope()

    def addField(self, field_ti, field_obj):
        if field_obj is not None:
            self._lib_typeobj.addField(field_obj)
        field_ti.idx = len(self._field_typeinfo)
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

