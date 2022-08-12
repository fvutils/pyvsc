#****************************************************************************
#* Created on Feb 26, 2022
#*
#* @author: mballance
#****************************************************************************
from dataclasses import _MISSING_TYPE
import dataclasses

from vsc2.impl.field_scalar_impl import FieldScalarImpl
from vsc2.impl.scalar_t import ScalarT
from vsc2.types import rand
from libvsc import core
from vsc2.impl.ctor import Ctor
from vsc2.impl.randclass_typeinfo import RandClassTypeInfo
from vsc2.impl import ctor
from vsc2.impl.randclass_impl import RandClassImpl
from vsc2.impl.typeinfo import TypeInfo
from vsc2.impl.type_kind_e import TypeKindE
from vsc2.impl.field_typeinfo import FieldTypeInfo
from vsc2.impl.rand_t import RandT
from vsc2.impl.list_t import ListT

class RandClassDecoratorImpl(object):
    """Decorator implementation for @randclass and type-model building code"""
    
    def __init__(self, kwargs):
        pass
    
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
        return RandClassTypeInfo(ds_t)
    
    def __call__(self, T):
        ctor = Ctor.inst()
        Tp = dataclasses.dataclass(T, init=False)
        
        ds_t = self._getLibDataType(T.__qualname__)

        print("RandClass %s" % T.__qualname__)
        Tp._is_randclass = True
        Tp._typeinfo = RandClassTypeInfo(ds_t)
        
        print("  Bases: %s" % str(T.__bases__))
        
        constraints = Ctor.inst().pop_constraint_decl()
        Tp._typeinfo._constraint_l.extend(constraints)
        
        for c in constraints:
            Tp._typeinfo._constraint_m[c._name] = c
            
        for b in T.__bases__:
            if hasattr(b, "_typeinfo"):
                self.__collectConstraints(Tp._typeinfo, b)
            
        # Process dataclass fields to determine which 
        # require special treatment because they are 
        # PyVSC fields        
        idx = 0
        for f in dataclasses.fields(Tp):
            print("==> Field: %s type=%s" % (str(f), str(f.type))) 

            is_rand = False
            
            print("type(f.type)=%s" % str(type(f.type)))

            if issubclass(f.type, RandT):
                print("isrand")
                t = f.type.T
                print(f.type.T)
                is_rand = True
            else:
                t = f.type

            if issubclass(t, ScalarT):
                print("   Is a scalar: %d,%d" % (t.W, t.S))

                if f.name not in Tp._typeinfo._field_ctor_m.keys():
                    if not isinstance(f.default, dataclasses._MISSING_TYPE):
                        iv = f.default
                        if type(iv) != int:
                            raise Exception("Initial value for field %s (%s) is not integral" % (f.name, str(iv)))
                    else:
                        iv = 0
                        
                        
#                    setattr(Tp, f.name, property(FieldScalarImpl.__get__, FieldScalarImpl.__set__))
#                    setattr(Tp, f.name, FieldScalarDesc())
                    print("Register with is_rand=%d" % is_rand)
                    # Create a TypeField instance to represent the field
                    it = ctor.ctxt().findDataTypeInt(t.S, t.W)
                    if it is None:
                        it = ctor.ctxt().mkDataTypeInt(t.S, t.W)
                        ctor.ctxt().addDataTypeInt(it)
                        
                    attr = core.TypeFieldAttr.NoAttr
                    
                    if is_rand:
                        attr |= core.TypeFieldAttr.Rand

                    field_ti = FieldTypeInfo(
                        f.name, 
                        idx,
                        ctor.ctxt().mkTypeFieldPhy(
                            f.name,
                            it,
                            False,
                            attr,
                            None),
                            lambda self, name, lib_field, s=t.S: RandClassImpl.createPrimField(self, name, lib_field, s))
                    idx += 1
                    
                    Tp._typeinfo.addField(field_ti)
                    
                # TODO: fill in factory
            elif issubclass(t, ListT):
                print("  Is a list: %s" % str(t.T))
            else:
                raise Exception("Non-scalar fields are not yet supported")
#                print("   Is a scalar: %d,%d" % (f.type.W, f.type.S))
                pass
            
            print("<== Field: %s" % str(f)) 
            
        base_init = Tp.__init__
        Tp.__init__ = lambda self, *args, **kwargs: RandClassImpl.init(
            self, base_init, *args, *kwargs)
        Tp.randomize = lambda self: RandClassImpl.randomize(self)
        Tp.randomize_with = lambda self: RandClassImpl.randomize_with(self)
        Tp.__setattr__ = lambda self, name, val: RandClassImpl.setattr(self, name, val)
        Tp.__getattribute__ = lambda self, name: RandClassImpl.getattr(self, name)
        
        # Now, we need to build out the constraints
        # We first must create a temp object that can be used by the constraint builder

        # Push a frame for the object to find
        ctor.push_scope(None, ds_t, True)
        
        # Now, go create the object itself. Note that we're in
        # type mode, so type fields are built out
        obj = Tp()

        ctor.push_scope(obj, ds_t, True)
        ctor.push_expr_mode()        
        for c in Tp._typeinfo._constraint_l:
            cs = ctor.ctxt().mkTypeConstraintBlock(c.name)
            ctor.push_constraint_scope(cs)
            c(obj)
            ctor.pop_constraint_scope()
            Tp._typeinfo._lib_typeobj.addConstraint(cs)
        ctor.pop_expr_mode()
        ctor.pop_scope()
        
        return Tp
    
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

