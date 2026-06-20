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


# Per-TYPE cache attribute holding the root solve :class:`_Node`. The dc constraint
# model is type-stable (same structure for every instance), so we build it ONCE per
# type and rebind the current instance's values/rand_mode/writeback-target per call.
# Because the root model *object* is then shared across all instances, the
# Randomizer's Tier-A plan cache (keyed on the root object) — and the dv-solve
# per-RandSet compiled-problem cache below it — hit for every instance, not just for
# repeated randomize() of one object. This skips VariableBoundVisitor /
# ArrayConstraintBuilder / RandInfoBuilder and the native translation per instance.
#
# Caveat: the shared model carries the "current" instance's values, so randomize()
# is not re-entrant across instances of the same type (interleaving two instances'
# solves, or threading) — pyvsc is single-threaded/sequential by design.
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
    """Return the type's shared (composite, field_models), rebound to ``obj``'s
    current field values + rand_mode + writeback target. Built once per type and
    cached on the class; subsequent instances reuse the model object (so the
    plan/translation caches hit)."""
    cls = type(obj)
    # cls.__dict__ (not getattr) so a subclass doesn't inherit a base's model.
    node = cls.__dict__.get(_SOLVE_MODEL_ATTR)
    if node is not None:
        _apply_node(node, obj)
        return node.composite, node.field_models
    node = build_solve_node(obj, type_model)   # applies obj's inputs as it builds
    setattr(cls, _SOLVE_MODEL_ATTR, node)
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
        if fd.is_array and fd.elem_comp_cls is not None:
            arr, elem_nodes = _build_composite_array(obj, fd)
            composite.add_field(arr)
            field_models[fd.name] = arr
            children[fd.name] = elem_nodes
            if fd.is_rand_sz:
                composite.add_constraint(
                    _composite_array_size_bound(arr, fd.max_size))
            continue
        if fd.is_array:
            # Regular (scalar or enum-element) array — enum arrays carry enum_cls.
            fm = _build_array(fd)
        elif fd.enum_cls is not None:
            fm = EnumFieldModel(fd.name, EnumInfo.get(fd.enum_cls).enums, fd.is_rand)
        else:
            fm = FieldScalarModel(fd.name, fd.bits, fd.signed, fd.is_rand)
        composite.add_field(fm)
        field_models[fd.name] = fm

    # Lower the cached constraint programs against this instance's field models.
    # Generic/value programs are not added here (they apply only when referenced);
    # the registry is threaded in so references inside fixed blocks resolve.
    for prog in type_model.constraints:
        composite.add_constraint(ir_lower.lower_program(
            prog, field_models, type_model.generic_constraints))

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
    """Build a scalar- or enum-element FieldArrayModel. Fixed-size arrays
    (``size=N``) are pre-populated with N elements; random-size arrays start empty
    and are extended by the array-constraint builder up to the size field's solved
    bound (so the user must constrain ``arr.size``). For enum arrays, ``enums``
    makes ``add_field`` build EnumFieldModels constrained to the enum's values."""
    type_t = FieldScalarModel("<primitive>", fd.bits, fd.signed, fd.is_rand)
    enums = EnumInfo.get(fd.enum_cls).enums if fd.enum_cls is not None else None
    arr = FieldArrayModel(fd.name, type_t, True, enums,
                          fd.bits, fd.signed, fd.is_rand, fd.is_rand_sz)
    if not fd.is_rand_sz:
        for _ in range(fd.size):
            arr.add_field()
    return arr


def _build_composite_array(obj, fd):
    """Build a composite-element FieldArrayModel + a child _Node per element.

    Mirrors the classic ``rand_list_t(Sub())`` path: each element's
    FieldCompositeModel is appended to a non-scalar FieldArrayModel, so the
    backend sees the same model shape. Random-size arrays (``max_size=M``,
    rand ``size``) pre-allocate M element composites — the solver picks ``size``
    within [0, M] (the user constrains it) and writeback exposes ``size`` of
    them — matching classic, which pre-appends the elements then constrains size."""
    if fd.is_rand_sz and fd.max_size is None:
        raise NotImplementedError(
            "random-size composite array %r needs max_size= (the pre-allocation "
            "bound); fixed-size needs size=" % fd.name)
    elem_objs = getattr(obj, fd.name)
    elem_tm = fd.elem_type_model()
    arr = FieldArrayModel(fd.name, None, False, None, -1, -1, fd.is_rand,
                          fd.is_rand_sz)
    elem_nodes = []
    for elem_obj in elem_objs:
        elem_node = build_solve_node(elem_obj, elem_tm)
        arr.append(elem_node.composite)   # sets size, names elem, propagates rand
        elem_nodes.append(elem_node)
    return arr, elem_nodes


def _composite_array_size_bound(arr, max_size):
    """A 0 <= size <= max_size constraint pinning a random-size composite array's
    size to its pre-allocated element count (the user constrains it further)."""
    block = ConstraintBlockModel("__arrsz_%s__" % arr.name)
    size_ref = ExprFieldRefModel(arr.size)
    block.constraint_l.append(ConstraintExprModel(ExprBinModel(
        ExprFieldRefModel(arr.size), BinExprType.Ge, ExprLiteralModel(0, True, 32))))
    block.constraint_l.append(ConstraintExprModel(ExprBinModel(
        size_ref, BinExprType.Le, ExprLiteralModel(max_size, True, 32))))
    return block


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
        if fd.is_array and fd.elem_comp_cls is not None:
            if fd.is_rand_sz:
                # Random-size: obj.<arr> may have been truncated to the last
                # solved size, so refresh every pre-allocated element from the
                # instance the cached node already holds (not the truncated list).
                for en in node.children[fd.name]:
                    _apply_node(en, en.obj)
            else:
                for en, eo in zip(node.children[fd.name], getattr(obj, fd.name)):
                    _apply_node(en, eo)
            continue
        fm = field_models[fd.name]
        enabled = True
        if fd.is_rand and rand_mode is not None and rand_mode.get(fd.name) is False:
            enabled = False
        if fd.is_array:
            cur = getattr(obj, fd.name, None) or []
            ei = EnumInfo.get(fd.enum_cls) if fd.enum_cls is not None else None
            for i, e in enumerate(fm.field_l):
                v = cur[i] if i < len(cur) else 0
                if ei is not None:
                    # Enum element: member -> value via EnumInfo, else raw int.
                    e.set_val(ei.e2v(v) if isinstance(v, _Enum) else int(v))
                else:
                    e.set_val(ValueScalar(_coerce(fd, v)))
                if fd.is_rand:
                    e.rand_mode = enabled
            continue
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
        if fd.is_rand:
            # Per-instance rand_mode override: a disabled rand field becomes a
            # constant at its current value (set_used_rand honors rand_mode level>0).
            fm.rand_mode = enabled
        fm.set_val(ValueScalar(_coerce(fd, getattr(obj, fd.name, 0))))

    # Per-instance constraint_mode: flip enabled on the named block models. The
    # plan-cache signature reads block.enabled, so a toggle forces a re-solve.
    cmode = getattr(obj, "_vsc_constraint_mode", None)
    if cmode:
        for blk in node.composite.constraint_model_l:
            if blk.name in cmode:
                blk.enabled = cmode[blk.name]


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
        # Composite-array elements write themselves back via their own _RandIf
        # (FieldArrayModel.post_randomize walks the element composites). For a
        # random-size array, expose exactly the solved-``size`` element instances.
        if fd.is_array and fd.elem_comp_cls is not None:
            if fd.is_rand_sz:
                arr = field_models[fd.name]
                n = int(arr.size.get_val())
                instances = [en.obj for en in node.children[fd.name]]
                object.__setattr__(obj, fd.name, instances[:n])
            continue
        fm = field_models[fd.name]
        if fd.is_array:
            # The visible length is the (solved) size field — for random-size
            # arrays field_l is over-allocated to the max bound. Enum arrays write
            # back enum members.
            n = int(fm.size.get_val())
            if fd.enum_cls is not None:
                ei = EnumInfo.get(fd.enum_cls)
                object.__setattr__(obj, fd.name,
                                   [ei.v2e(int(fm.field_l[i].get_val().v))
                                    for i in range(n)])
            else:
                object.__setattr__(obj, fd.name,
                                   [int(fm.field_l[i].get_val().v) for i in range(n)])
        elif fd.enum_cls is not None:
            # Store the enum member (matches classic type_enum.get_val).
            object.__setattr__(obj, fd.name,
                               EnumInfo.get(fd.enum_cls).v2e(int(fm.get_val().v)))
        else:
            # .v is the raw Python int (avoids the ValueInt __int__ deprecation path).
            object.__setattr__(obj, fd.name, int(fm.get_val().v))
