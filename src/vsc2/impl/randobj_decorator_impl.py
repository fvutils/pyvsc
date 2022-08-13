'''
Created on May 22, 2022

@author: mballance
'''
from vsc2.impl.ctor import Ctor
from vsc2.impl.typeinfo_randclass import TypeInfoRandClass
from vsc2.impl.randobj_impl import RandObjImpl
from vsc2.impl.type_kind_e import TypeKindE


class RandObjDecoratorImpl(object):
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        ctor = Ctor.inst()
        
        T._typeinfo = RandClassTypeInfo(None, TypeKindE.RandObj)
        
        RandObjImpl.addMethods(T)
        
        constraints = Ctor.inst().pop_constraint_decl()
        T._typeinfo._constraint_l.extend(constraints)
        
        for c in constraints:
            T._typeinfo._constraint_m[c._name] = c
            
        for b in T.__bases__:
            if hasattr(b, "_typeinfo"):
                self.__collectConstraints(T._typeinfo, b)
                
        print("Constraints: %s" % str(T._typeinfo._constraint_l))
        
        return T
    
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

