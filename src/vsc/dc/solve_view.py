"""
Per-instance solve view: materialize a ``FieldCompositeModel`` (FieldScalarModels +
lowered constraint blocks) from a cached :class:`TypeModel` and the instance's
current field values, hand it to the existing ``Randomizer``, and write the solved
values back onto the instance.

The model objects are rebuilt per randomize call (cheap — no source parse, no
``dir()`` scan), and field references are bound by name to *this* instance's scalar
models. The expensive type-level work (AST parse, field discovery) was done once.
"""
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from enum import Enum as _Enum

from vsc.impl.enum_info import EnumInfo
from vsc.model.enum_field_model import EnumFieldModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.value_scalar import ValueScalar

from . import ir_lower


# Per-instance cache attribute holding the root solve :class:`_Node`. Reusing the
# model object across randomize() calls both skips the rebuild/re-lower below and
# lets the Randomizer's per-object Tier-A plan cache (keyed on the root model
# object) hit across calls — a strict superset of today's per-object caching.
_SOLVE_MODEL_ATTR = "_vsc_solve_model"


class _Node:
    """One level of the solve tree: a ``FieldCompositeModel`` plus the bookkeeping
    needed to refresh inputs and write solved values back. Composite (nested
    ``RandClass``) fields get a child ``_Node`` so apply/writeback recurse."""
    __slots__ = ("obj", "tm", "composite", "field_models", "children")

    def __init__(self, obj, tm, composite, field_models, children):
        self.obj = obj
        self.tm = tm
        self.composite = composite
        self.field_models = field_models   # name -> leaf/array/enum/child-composite model
        self.children = children           # name -> child _Node (composite fields)


def get_solve_model(obj, type_model):
    """Return a cached-or-freshly-built (composite, field_models) for ``obj``,
    with field values + rand_mode refreshed from the current instance state."""
    node = getattr(obj, _SOLVE_MODEL_ATTR, None)
    if node is not None:
        _apply_node(node, obj)
        return node.composite, node.field_models
    node = build_solve_node(obj, type_model)
    object.__setattr__(obj, _SOLVE_MODEL_ATTR, node)
    return node.composite, node.field_models


class _RandIf:
    """Bridges one composite's pre/post-randomize callbacks to its instance.

    ``do_post_randomize`` runs *during* ``do_randomize`` (after the solve). Each
    level writes back only *its own* leaf fields; ``FieldCompositeModel`` walks the
    nested composites so every level's ``_RandIf`` fires. Writeback precedes the
    user hook so ``post_randomize`` sees randomized values and its edits stick."""

    def __init__(self, node):
        self._node = node

    def do_pre_randomize(self):
        hook = getattr(self._node.obj, "pre_randomize", None)
        if callable(hook):
            hook()

    def do_post_randomize(self):
        _writeback_level(self._node)
        hook = getattr(self._node.obj, "post_randomize", None)
        if callable(hook):
            hook()


def build_solve_node(obj, type_model):
    """Build a fresh solve :class:`_Node` for ``obj`` (recursing into composites)."""
    composite = FieldCompositeModel(type_model.cls_name, True, None)
    composite.typename = type_model.cls_name

    field_models = {}
    children = {}
    for fd in type_model.fields:
        if fd.is_opaque:
            continue   # plain Python state — never enters the solve model
        if fd.is_composite:
            child_obj = getattr(obj, fd.name)
            child_node = build_solve_node(child_obj, fd.comp_type_model())
            # Re-name the child composite to the field name so cross-references
            # (self.sub.x) and fullnames read naturally in the parent's tree.
            child_node.composite.name = fd.name
            child_node.composite.is_declared_rand = fd.is_rand
            composite.add_field(child_node.composite)
            field_models[fd.name] = child_node.composite
            children[fd.name] = child_node
            continue
        if fd.enum_cls is not None:
            fm = EnumFieldModel(fd.name, EnumInfo.get(fd.enum_cls).enums, fd.is_rand)
        elif fd.is_array:
            fm = _build_array(fd)
        else:
            fm = FieldScalarModel(fd.name, fd.bits, fd.signed, fd.is_rand)
        composite.add_field(fm)
        field_models[fd.name] = fm

    # Lower the cached constraint programs against this instance's field models.
    for prog in type_model.constraints:
        composite.add_constraint(ir_lower.lower_program(prog, field_models))

    # Synthesize domain (lo<=f<=hi) constraints for rand(domain=...) fields.
    dom = _domain_block(type_model, field_models)
    if dom is not None:
        composite.add_constraint(dom)

    node = _Node(obj, type_model, composite, field_models, children)
    # Bridge this level's pre/post_randomize hooks (and writeback) to the instance.
    composite.rand_if = _RandIf(node)

    _apply_node(node, obj)
    return node


def _build_array(fd):
    """Build a scalar FieldArrayModel. Fixed-size arrays (``size=N``) are
    pre-populated with N elements; random-size arrays start empty and are extended
    by the array-constraint builder up to the size field's solved bound (so the
    user must constrain ``arr.size``)."""
    type_t = FieldScalarModel("<primitive>", fd.bits, fd.signed, fd.is_rand)
    arr = FieldArrayModel(fd.name, type_t, True, None,
                          fd.bits, fd.signed, fd.is_rand, fd.is_rand_sz)
    if not fd.is_rand_sz:
        for _ in range(fd.size):
            arr.add_field()
    return arr


def _coerce(fd, v):
    v = int(v)
    return v if fd.signed else (v & ((1 << fd.bits) - 1))


def _apply_node(node, obj):
    """Set each field model's current value (from ``obj``) and rand_mode (from any
    per-instance override), recursing into composite children. Run on every solve
    so model reuse stays correct (and tracks a replaced nested instance)."""
    node.obj = obj
    type_model = node.tm
    field_models = node.field_models
    rand_mode = getattr(obj, "_vsc_rand_mode", None)
    for fd in type_model.fields:
        if fd.is_opaque:
            continue
        if fd.is_composite:
            _apply_node(node.children[fd.name], getattr(obj, fd.name))
            continue
        fm = field_models[fd.name]
        enabled = True
        if fd.is_rand and rand_mode is not None and rand_mode.get(fd.name) is False:
            enabled = False
        if fd.enum_cls is not None:
            if fd.is_rand:
                fm.rand_mode = enabled
            cur = getattr(obj, fd.name, None)
            # Instance value may be an enum member or a raw int. Members go through
            # EnumInfo so plain (non-Int) enums map by index, not int().
            if isinstance(cur, _Enum):
                fm.set_val(EnumInfo.get(fd.enum_cls).e2v(cur))
            elif cur is not None:
                fm.set_val(int(cur))
            else:
                fm.set_val(fm.enums[0])
            continue
        if fd.is_array:
            cur = getattr(obj, fd.name, None) or []
            for i, e in enumerate(fm.field_l):
                e.set_val(ValueScalar(_coerce(fd, cur[i] if i < len(cur) else 0)))
                if fd.is_rand:
                    e.rand_mode = enabled
            continue
        if fd.is_rand:
            # Per-instance rand_mode override: a disabled rand field becomes a
            # constant at its current value (set_used_rand honors rand_mode level>0).
            fm.rand_mode = enabled
        fm.set_val(ValueScalar(_coerce(fd, getattr(obj, fd.name, 0))))


def _domain_block(type_model, field_models):
    block = None
    for fd in type_model.fields:
        if fd.is_rand and fd.domain is not None:
            lo, hi = fd.domain
            if block is None:
                block = ConstraintBlockModel("__domain__")
            ref = ExprFieldRefModel(field_models[fd.name])
            block.constraint_l.append(ConstraintExprModel(ExprBinModel(
                ExprFieldRefModel(field_models[fd.name]), BinExprType.Ge,
                ExprLiteralModel(lo, True, 32))))
            block.constraint_l.append(ConstraintExprModel(ExprBinModel(
                ref, BinExprType.Le, ExprLiteralModel(hi, True, 32))))
    return block


def _writeback_level(node):
    """Copy solved values from this level's leaf field models back onto its
    instance. Nested composites are written by their own ``_RandIf`` (driven by
    ``FieldCompositeModel.post_randomize``), so this never recurses."""
    obj = node.obj
    field_models = node.field_models
    for fd in node.tm.fields:
        if fd.is_composite or not fd.is_rand:
            continue
        fm = field_models[fd.name]
        if fd.enum_cls is not None:
            # Store the enum member (matches classic type_enum.get_val).
            object.__setattr__(obj, fd.name,
                               EnumInfo.get(fd.enum_cls).v2e(int(fm.get_val().v)))
        elif fd.is_array:
            # The visible length is the (solved) size field — for random-size
            # arrays field_l is over-allocated to the max bound.
            n = int(fm.size.get_val())
            object.__setattr__(obj, fd.name,
                               [int(fm.field_l[i].get_val().v) for i in range(n)])
        else:
            # .v is the raw Python int (avoids the ValueInt __int__ deprecation path).
            object.__setattr__(obj, fd.name, int(fm.get_val().v))
