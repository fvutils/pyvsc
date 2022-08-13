#****************************************************************************
#* Created on Feb 26, 2022
#*
#* @author: mballance
#****************************************************************************
from dataclasses import _MISSING_TYPE
import dataclasses
import typeworks
from .constraint_decorator_impl import ConstraintDecoratorImpl

from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.scalar_t import ScalarT
from libvsc import core
from vsc2.impl.ctor import Ctor
from vsc2.impl.typeinfo_randclass import TypeInfoRandClass
from vsc2.impl.randclass_impl import RandClassImpl
from vsc2.impl.typeinfo_vsc import TypeInfoVsc
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo_field import TypeInfoField
from vsc2.impl.rand_t import RandT
from vsc2.impl.list_t import ListT

class RandClassDecoratorImpl(typeworks.ClsDecoratorBase):
    """Decorator implementation for @randclass and type-model building code"""
    
    def __init__(self, args, kwargs):
        super().__init__(args, kwargs)
        self._field_idx = 0
        
    def get_type_category(self):
        return TypeKindE.RandClass
    
    def _getLibDataType(self, name):
        ctor = Ctor.inst()

        ds_t = ctor.ctxt().findDataTypeStruct(name)
        
        if ds_t is not None:
            raise Exception("Type already registered")
        else:
            ds_t = ctor.ctxt().mkDataTypeStruct(name)
            ctor.ctxt().addDataTypeStruct(ds_t)
        
        return ds_t
    
    def _createTypeInfo(self, ds_t):
        return TypeInfoRandClass(ds_t)
    
    def pre_decorate(self, T):
        # Ensure we've created type-info of appropriate type
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        
        randclass_ti.lib_typeobj = self._getLibDataType(T.__qualname__)

        print("RandClass %s" % T.__qualname__)
        print("  Bases: %s" % str(T.__bases__))

        constraints = typeworks.DeclRgy.pop_decl(ConstraintDecoratorImpl)
        randclass_ti.addConstraints(constraints)
        
        for b in T.__bases__:
            info = typeworks.TypeInfo.get(b, False)
            if info is not None:
                b_randclass_info = TypeInfoRandClass.get(info, False)
                if b_randclass_info is not None:
                    self.__collectConstraints(b_randclass_info, b)        
                
        super().pre_decorate(T)
        
    def init_annotated_field(self, key, value, has_init, init):
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        is_rand = False
            
        print("type(value)=%s" % str(type(value)))

        if issubclass(value, RandT):
            print("isrand")
            t = value.T
            is_rand = True
        else:
            t = value

        if issubclass(t, ScalarT):
            ctor = Ctor.inst()
            print("   Is a scalar: %d,%d" % (t.W, t.S))

            if has_init:
                iv = init
            else:
                iv = 0
                
            # Create a TypeField instance to represent the field
            it = ctor.ctxt().findDataTypeInt(t.S, t.W)
            if it is None:
                it = ctor.ctxt().mkDataTypeInt(t.S, t.W)
                ctor.ctxt().addDataTypeInt(it)
                        
            attr = core.TypeFieldAttr.NoAttr
                    
            if is_rand:
                attr |= core.TypeFieldAttr.Rand

            field_ti = TypeInfoField(
                key, 
                self._field_idx,
                ctor.ctxt().mkTypeFieldPhy(
                    key,
                    it,
                    False,
                    attr,
                    None), # TODO: initial value
                lambda self, name, lib_field, s=t.S: RandClassImpl.createPrimField(self, name, lib_field, s))
            randclass_ti.addField(field_ti)
            self._field_idx += 1
            self.set_field_initial(key, None)
        elif issubclass(t, ListT):
            print("  Is a list: %s" % str(t.T))
        else:
            raise Exception("Non-scalar fields are not yet supported")
    
    # def __call__(self, T):
    #     ctor = Ctor.inst()
    #     Tp = dataclasses.dataclass(T, init=False)
        

            
    #     # Process dataclass fields to determine which 
    #     # require special treatment because they are 
    #     # PyVSC fields        
    #     idx = 0
    #     for f in dataclasses.fields(Tp):
    #         print("==> Field: %s type=%s" % (str(f), str(f.type))) 


            
    #         print("<== Field: %s" % str(f)) 
            

        

        
    #     return Tp

    def post_decorate(self, T, Tp):
        ctor = Ctor.inst()
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        super().post_decorate(T, Tp)
        
        # Add methods
        base_init = Tp.__init__
        Tp.__init__ = lambda self, *args, **kwargs: RandClassImpl.init(
            self, base_init, *args, *kwargs)
        Tp.randomize = lambda self: RandClassImpl.randomize(self)
        Tp.randomize_with = lambda self: RandClassImpl.randomize_with(self)
        Tp.__setattr__ = lambda self, name, val: RandClassImpl.setattr(self, name, val)
        Tp.__getattribute__ = lambda self, name: RandClassImpl.getattr(self, name)        
        
        # Finish elaborating the type object by building out the constraints
        # We first must create a temp object that can be used by the constraint builder

        # Push a frame for the object to find
        ctor.push_scope(None, randclass_ti.lib_typeobj, True)
        
        # Now, go create the object itself. Note that we're in
        # type mode, so type fields are built out
        obj = Tp()

        ctor.push_scope(obj, randclass_ti.lib_typeobj, True)
        ctor.push_expr_mode()        
        for c in randclass_ti.getConstraints():
            cs = ctor.ctxt().mkTypeConstraintBlock(c.name)
            ctor.push_constraint_scope(cs)
            c(obj)
            ctor.pop_constraint_scope()
            randclass_ti.lib_typeobj.addConstraint(cs)
        ctor.pop_expr_mode()
        ctor.pop_scope()        
        
    
    def __collectConstraints(self, typeinfo, clsT):
        """Connect constraints from base classes"""
        # First, connect any additional constraints registered in the base class
        for cn,cd in clsT._typeinfo._constraint_m.items():
            if cn not in typeinfo._constraint_m.keys():
                print("Adding base-class %s" % cn)
                typeinfo._constraint_l.append(cd)
                typeinfo._constraint_m[cn] = cd
            else:
                print("Skipping overridden %s" % cn)
                pass
                
        # Now, keep digging
        for b in clsT.__bases__:
            if hasattr(b, "_typeinfo"):
                self.__collectConstraints(typeinfo, b)

