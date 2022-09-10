#****************************************************************************
#* Created on Feb 26, 2022
#*
#* @author: mballance
#****************************************************************************
import typeworks
from vsc2.impl.typeinfo_scalar import TypeInfoScalar
from .constraint_decorator_impl import ConstraintDecoratorImpl

from vsc2.impl.scalar_t import ScalarT
from libvsc import core
from vsc2.impl.ctor import Ctor
from vsc2.impl.typeinfo_randclass import TypeInfoRandClass
from vsc2.impl.randclass_impl import RandClassImpl
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.typeinfo_field import TypeInfoField
from vsc2.impl.rand_t import RandT
from vsc2.impl.list_t import ListT

class RandClassDecoratorImpl(typeworks.ClsDecoratorBase):
    """Decorator implementation for @randclass and type-model building code"""
    
    def __init__(self, args, kwargs):
        super().__init__(args, kwargs)
        
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
        print("RandClasss.PreDecorate")
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        
        print("  TI: %s" % str(randclass_ti))
        
        randclass_ti.lib_typeobj = self._getLibDataType(T.__qualname__)

        print("RandClass %s" % T.__qualname__)
        print("  Bases: %s" % str(T.__bases__))
        print("  TI: %s ; lib_typeobj: %s" % (str(randclass_ti), str(randclass_ti.lib_typeobj)))

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
                iv = ctor.ctxt().mkModelVal()
                iv.setBits(t.W)
                if t.S:
                    iv.set_val_i(init)
                else:
                    iv.set_val_u(init)
            else:
                iv = None
                
            # Create a TypeField instance to represent the field
            it = ctor.ctxt().findDataTypeInt(t.S, t.W)
            if it is None:
                it = ctor.ctxt().mkDataTypeInt(t.S, t.W)
                ctor.ctxt().addDataTypeInt(it)
                        
            attr = core.TypeFieldAttr.NoAttr
                    
            if is_rand:
                attr |= core.TypeFieldAttr.Rand

            field_type_obj = ctor.ctxt().mkTypeFieldPhy(
                key,
                it,
                False,
                attr,
                iv) # TODO: initial value

            field_ti = TypeInfoField(key, TypeInfoScalar(t.S))
            randclass_ti.addField(field_ti, field_type_obj)
            self.set_field_initial(key, None)
        elif issubclass(t, ListT):
            print("  Is a list: %s" % str(t.T))
        else:
            raise Exception("Non-scalar fields are not yet supported")
    
    def post_decorate(self, T, Tp):
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        super().post_decorate(T, Tp)
        
        # Add methods
        randclass_ti._base_init = Tp.__init__
        RandClassImpl.addMethods(Tp)
        

    def pre_register(self):
        # Finish elaborating the type object by building out the constraints
        # We first must create a temp object that can be used by the constraint builder

        self.elab_type()

    def elab_type(self):
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())
        obj = self.create_type_inst()
        randclass_ti.elab(obj)

    def create_type_inst(self):
        """
        Creates the object instance used for type elaboration
        """
        ctor = Ctor.inst()
        randclass_ti = TypeInfoRandClass.get(self.get_typeinfo())

        # Push a frame for the object to find
        print("create_type: lib_typeobj=%s" % str(randclass_ti.lib_typeobj))
        ctor.push_scope(None, randclass_ti.lib_typeobj, True)
        
        # Now, go create the object itself. Note that we're in
        # type mode, so type fields are built out
        obj = self.get_typeinfo().Tp()

        # Note: creation of the object pops the stack frame we pushed

        return obj

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

