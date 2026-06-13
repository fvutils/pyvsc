"""
TypeModel — the per-type, instance-independent elaboration of a ``@vdc.dataclass``
``RandClass``: its field layout plus its compiled constraint programs. Built once
(at decoration time) and cached on the class as ``cls._vsc_type_model``.

See ``doc/notes/dataclass_pyvsc_impl_test_doc_plan.md`` §2.3.
"""
import dataclasses
import typing
import warnings
from enum import EnumMeta

from .constraint_parser import parse_constraint
from .fields import get_field_meta
from .types import width_of

# Attribute used to tag a method as a constraint (set by @vdc.constraint).
CONSTRAINT_ATTR = "_vsc_dc_constraint"

# Default width for an annotated-but-unwidth'd / bitv field lacking an explicit width.
_DEFAULT_WIDTH = 32


class FieldDecl:
    """Type-level description of one random/state field. For arrays, ``bits`` and
    ``signed`` describe the *element* type."""
    __slots__ = ("name", "bits", "signed", "is_rand", "rand_kind",
                 "domain", "size", "max_size", "soft", "role",
                 "is_array", "is_rand_sz", "enum_cls", "is_opaque")

    def __init__(self, name, bits, signed, is_rand, rand_kind,
                 domain=None, size=None, max_size=None, soft=None, role="",
                 is_array=False, is_rand_sz=False, enum_cls=None, is_opaque=False):
        self.name = name
        self.bits = bits
        self.signed = signed
        self.is_rand = is_rand
        self.rand_kind = rand_kind      # "rand" | "randc" | ""
        self.domain = domain
        self.size = size
        self.max_size = max_size
        self.soft = soft
        self.role = role
        self.is_array = is_array
        self.is_rand_sz = is_rand_sz
        self.enum_cls = enum_cls        # IntEnum class, or None
        # Opaque = plain Python state (lists, objects, ...) the solver ignores
        # entirely: not in the model, not constrainable, not written back.
        self.is_opaque = is_opaque

    def __repr__(self):
        if self.is_array:
            return "FieldDecl(%s: list[%s%d] x%s rand=%s)" % (
                self.name, "s" if self.signed else "u", self.bits,
                self.size, self.is_rand)
        return "FieldDecl(%s u%d%s rand=%s)" % (
            self.name, self.bits, "s" if self.signed else "", self.is_rand)


class TypeModel:
    __slots__ = ("cls_name", "fields", "field_index", "constraints", "layout_hash")

    def __init__(self, cls_name, fields, constraints):
        self.cls_name = cls_name
        self.fields = fields
        self.field_index = {f.name: i for i, f in enumerate(fields)}
        self.constraints = constraints
        self.layout_hash = _layout_hash(cls_name, fields)

    def rand_fields(self):
        return [f for f in self.fields if f.is_rand]

    def __repr__(self):
        return "TypeModel(%s, %d fields, %d constraints)" % (
            self.cls_name, len(self.fields), len(self.constraints))


def _layout_hash(cls_name, fields):
    sig = (cls_name,) + tuple(
        (f.name, f.bits, f.signed, f.rand_kind) for f in fields)
    return hash(sig)


def _resolve_width(meta, annotation):
    """Return (bits, signed) for a field from its annotation/metadata."""
    if meta is not None and meta.width is not None:
        return meta.width, bool(meta.signed)
    w = width_of(annotation)
    if w is not None:
        bits, signed = w
        if bits < 0:   # bitv with no explicit width
            return _DEFAULT_WIDTH, signed
        return bits, signed
    # Bare int (or unknown): default width, signed.
    return _DEFAULT_WIDTH, True


def _is_scalarish(annotation):
    """True if ``annotation`` denotes a solver scalar (a width-typed int alias, a
    bare int/bool, or unknown). Used to decide whether a non-rand field is opaque."""
    if annotation is None:
        return True
    if width_of(annotation) is not None:
        return True
    return annotation in (int, bool)


def _list_element(annotation):
    """If ``annotation`` is ``list[T]`` (or ``List[T]``), return ``T``; else None."""
    origin = typing.get_origin(annotation)
    if origin is list:
        args = typing.get_args(annotation)
        if args:
            return args[0]
    return None


def _array_decl(name, meta, elem_ann):
    """Build a FieldDecl for a ``list[T]`` field."""
    w = width_of(elem_ann)
    if w is not None and w[0] >= 0:
        bits, signed = w
    else:
        bits, signed = _DEFAULT_WIDTH, True
    if meta is not None and meta.width is not None:
        bits, signed = meta.width, bool(meta.signed)
    is_rand = meta.is_rand if meta is not None else False
    size = meta.size if meta is not None else None
    max_size = meta.max_size if meta is not None else None
    # Phase 2: fixed-size arrays (size given). Random-size (max_size / unbounded)
    # is a follow-on; flag it so the solve view can reject clearly for now.
    is_rand_sz = (size is None)
    return FieldDecl(
        name=name, bits=bits, signed=signed, is_rand=is_rand,
        rand_kind=(meta.role if (meta is not None and meta.is_rand) else ""),
        size=size, max_size=max_size,
        soft=(meta.soft if meta is not None else None),
        role=(meta.role if meta is not None else ""),
        is_array=True, is_rand_sz=is_rand_sz)


def _collect_constraints(cls):
    """Gather constraint methods across the MRO (subclass overrides win),
    preserving declaration order within each class."""
    seen = set()
    progs = []
    for klass in cls.__mro__:
        for name, member in vars(klass).items():
            if name in seen:
                continue
            if callable(member) and getattr(member, CONSTRAINT_ATTR, False):
                seen.add(name)
                prog = parse_constraint(name, member)
                if prog is not None:
                    progs.append(prog)
                else:
                    # Source unavailable (REPL/exec). Dropping the constraint
                    # silently would produce wrong results, so warn loudly. The
                    # Strategy-B template-eval fallback (plan §6 risk 2) lands later.
                    warnings.warn(
                        "vsc.dc: cannot read source for constraint %r on %s "
                        "(defined in a REPL/exec?); the constraint is NOT applied"
                        % (name, cls.__qualname__),
                        RuntimeWarning, stacklevel=3)
    return progs


def build_type_model(cls):
    """Build (and return) the :class:`TypeModel` for a dataclass ``RandClass``."""
    hints = typing.get_type_hints(cls, include_extras=True)
    fields = []
    for f in dataclasses.fields(cls):
        meta = get_field_meta(f)
        ann = hints.get(f.name)
        if isinstance(ann, EnumMeta):
            # Enum field: annotation is an IntEnum class.
            fields.append(FieldDecl(
                f.name, 32, True,
                is_rand=(meta.is_rand if meta is not None else False),
                rand_kind=(meta.role if (meta is not None and meta.is_rand) else ""),
                role=(meta.role if meta is not None else ""),
                enum_cls=ann))
            continue
        elem_ann = _list_element(ann)
        if elem_ann is not None:
            # Array field: list[T]. Element width comes from T; size from metadata.
            fields.append(_array_decl(f.name, meta, elem_ann))
            continue
        is_rand = meta.is_rand if meta is not None else False
        if not is_rand and not _is_scalarish(ann):
            # Non-rand field of a non-solver type (list, dict, object, ...): opaque
            # Python state. Kept off the model so pre/post_randomize can use it freely.
            fields.append(FieldDecl(f.name, 0, False, False, "", role="",
                                    is_opaque=True))
            continue
        if meta is None:
            # A plain dataclass field with no vdc metadata: treat as non-rand state.
            bits, signed = _resolve_width(None, ann)
            fields.append(FieldDecl(f.name, bits, signed, False, "", role=""))
            continue
        bits, signed = _resolve_width(meta, ann)
        fields.append(FieldDecl(
            name=f.name, bits=bits, signed=signed,
            is_rand=meta.is_rand, rand_kind=meta.role if meta.is_rand else "",
            domain=meta.domain, size=meta.size, max_size=meta.max_size,
            soft=meta.soft, role=meta.role))

    constraints = _collect_constraints(cls)

    # A constraint method and a field cannot share a name: the method would shadow
    # the field's dataclass default and corrupt both. Catch it with a clear error
    # rather than a downstream TypeError.
    field_names = {f.name for f in fields}
    for prog in constraints:
        if prog.name in field_names:
            raise TypeError(
                "%s: constraint method %r collides with a field of the same name; "
                "rename the constraint (e.g. %r)"
                % (cls.__qualname__, prog.name, prog.name + "_c"))

    return TypeModel(cls.__qualname__, fields, constraints)
