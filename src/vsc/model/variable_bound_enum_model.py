'''
Created on Jun 2, 2020

@author: ballance
'''
from vsc.model.variable_bound_model import VariableBoundModel
from vsc.model.enum_field_model import EnumFieldModel


# Domain template per enum value list, built once: id(enums) -> (enums, ranges).
# The list object is held so its id can't be reused by another list.
#
# A fully contiguous enum is one range [lo, hi]. Any other keeps one range per
# value, as before: the Boolector swizzler picks a range uniformly and then a
# value inside it, so merging the runs of a gapped enum would bias it toward
# the values in shorter runs. One range per value, or a single range, both give
# every value the same chance.
_TEMPLATES = {}


def _template(enums):
    t = _TEMPLATES.get(id(enums))
    if t is not None and t[0] is enums:
        return t[1]
    vals = sorted(set(int(v) for v in enums))
    if vals and vals[-1] - vals[0] == len(vals) - 1:
        ranges = ((vals[0], vals[-1]),)
    else:
        ranges = tuple((v, v) for v in vals)
    _TEMPLATES[id(enums)] = (enums, ranges)
    return ranges


class VariableBoundEnumModel(VariableBoundModel):

    def __init__(self, var : EnumFieldModel):
        super().__init__(var)
        # Fresh inner lists: the propagators narrow ranges in place.
        self.domain.range_l = [[lo, hi] for lo, hi in _template(var.enums)]

