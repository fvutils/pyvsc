'''
Created on Mar 27, 2020

@author: ballance
'''
from typing import Dict
from enum import IntEnum, EnumMeta, Flag, Enum
from vsc.model.expr_literal_model import ExprLiteralModel

class _EnumValues(list):
    """An enum type's value list, shared by every field of that type.

    Read-only once built. Copying an object copies its fields, and each
    enum field's model holds this list: without sharing, `copy.deepcopy` of
    an instruction in riscv-dv duplicated a 497-entry list per field."""

    def __deepcopy__(self, memo):
        return self


class EnumInfo(object):
    """Collects information needed by VSC.

    One per enum type (EnumInfo.get interns them) and read-only, so a copied
    object shares its fields' EnumInfo instead of duplicating the maps."""
    
    _info_map : Dict[object,'EnumInfo'] = {}
    
    def __init__(self, e):
        self.e = e
        self.e2v_m = {}
        self.v2e_m = {}
        self.enums = []

        if isinstance(e, EnumMeta):
            i=0
            for en in e:
                # An IntEnum exposes its value via an __int__ method
                if hasattr(en, "__int__"):
                    i = int(en)
                    
                self.e2v_m[en] = i
                self.v2e_m[i] = en
                self.enums.append(i)
                i += 1
        else:
            raise Exception("unsupported enum type " + str(e))
        self.enums = _EnumValues(self.enums)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self
        
    def e2v(self, ev)->int:
        return self.e2v_m[ev]
    
    def v2e(self, v):
        return self.v2e_m[int(v)]
    
    def e2e(self, ev):
        v = self.e2v_m[ev]
        return ExprLiteralModel(v, True, 32)
    
    @staticmethod
    def get(e)->'EnumInfo':
        if not e in EnumInfo._info_map.keys():
            info = EnumInfo(e)
            EnumInfo._info_map[e] = info
        else:
            info = EnumInfo._info_map[e]
            
        return info
            
            
        