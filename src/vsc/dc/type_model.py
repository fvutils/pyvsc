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

from . import constraint_ir as _ir
from .constraint_parser import ConstraintParseError, parse_constraint
from .fields import get_field_meta, META_KEY
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
                 "is_array", "is_rand_sz", "enum_cls", "is_opaque",
                 "is_composite", "comp_cls", "elem_comp_cls")

    def __init__(self, name, bits, signed, is_rand, rand_kind,
                 domain=None, size=None, max_size=None, soft=None, role="",
                 is_array=False, is_rand_sz=False, enum_cls=None, is_opaque=False,
                 is_composite=False, comp_cls=None, elem_comp_cls=None):
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
        # Composite = a field typed as another @vdc.dataclass RandClass; its model
        # is a nested FieldCompositeModel stitched into the parent's solve tree.
        self.is_composite = is_composite
        self.comp_cls = comp_cls        # the nested RandClass, or None
        # For an array of composites (list[Sub] where Sub is a RandClass): the
        # element RandClass. Paired with is_array=True.
        self.elem_comp_cls = elem_comp_cls

    def comp_type_model(self):
        """Return the nested :class:`TypeModel` for a composite field (built and
        cached lazily on the nested class if the decorator was skipped)."""
        return _type_model_of(self.comp_cls)

    def elem_type_model(self):
        """Return the element :class:`TypeModel` for a composite array field."""
        return _type_model_of(self.elem_comp_cls)

    def __repr__(self):
        if self.is_array:
            return "FieldDecl(%s: list[%s%d] x%s rand=%s)" % (
                self.name, "s" if self.signed else "u", self.bits,
                self.size, self.is_rand)
        return "FieldDecl(%s u%d%s rand=%s)" % (
            self.name, self.bits, "s" if self.signed else "", self.is_rand)


class TypeModel:
    __slots__ = ("cls_name", "fields", "field_index", "constraints",
                 "generic_constraints", "layout_hash")

    def __init__(self, cls_name, fields, constraints, generic_constraints=None):
        self.cls_name = cls_name
        self.fields = fields
        self.field_index = {f.name: i for i, f in enumerate(fields)}
        # Fixed (always-on) constraint programs.
        self.constraints = constraints
        # Generic/value programs, keyed by name — applied only when referenced.
        self.generic_constraints = generic_constraints or {}
        self.layout_hash = _layout_hash(cls_name, fields)

    def rand_fields(self):
        return [f for f in self.fields if f.is_rand]

    def __repr__(self):
        return "TypeModel(%s, %d fields, %d constraints, %d generic)" % (
            self.cls_name, len(self.fields), len(self.constraints),
            len(self.generic_constraints))


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


def _enum_array_decl(name, meta, enum_cls):
    """Build a FieldDecl for a ``list[MyEnum]`` enum-array field."""
    size = meta.size if meta is not None else None
    is_rand = meta.is_rand if meta is not None else False
    return FieldDecl(
        name=name, bits=_DEFAULT_WIDTH, signed=False, is_rand=is_rand,
        rand_kind=(meta.role if (meta is not None and meta.is_rand) else ""),
        role=(meta.role if meta is not None else ""),
        size=size, max_size=(meta.max_size if meta is not None else None),
        is_array=True, is_rand_sz=(size is None), enum_cls=enum_cls)


def _composite_array_decl(name, meta, elem_cls):
    """Build a FieldDecl for a ``list[Sub]`` composite-array field (Sub a RandClass)."""
    size = meta.size if meta is not None else None
    is_rand = meta.is_rand if meta is not None else False
    # Random-size composite arrays (no size=) are a follow-on; the solve view
    # rejects them clearly for now.
    return FieldDecl(
        name=name, bits=0, signed=False, is_rand=is_rand,
        rand_kind=(meta.role if (meta is not None and meta.is_rand) else ""),
        role=(meta.role if meta is not None else ""),
        size=size, max_size=(meta.max_size if meta is not None else None),
        is_array=True, is_rand_sz=(size is None), elem_comp_cls=elem_cls)


def _collect_constraints(cls):
    """Gather constraint methods across the MRO (subclass overrides win),
    preserving declaration order within each class. Returns ``(fixed, generic)``:
    a list of fixed (always-on) programs and a name->program dict of generic/value
    programs (applied only when referenced)."""
    seen = {}        # name -> effective kind of the winning (most-derived) def
    fixed = []
    generic = {}
    for klass in cls.__mro__:
        for name, member in vars(klass).items():
            kind = getattr(member, CONSTRAINT_ATTR, None)
            if not (callable(member) and kind):
                continue
            marker = kind if isinstance(kind, str) else "fixed"
            if name in seen:
                # A base definition shadowed by a more-derived one: warn if the
                # override silently flips the constraint's kind (fixed<->generic
                # <->value) — that changes always-on-ness, a likely footgun.
                base_kind = _safe_kind(name, member, marker)
                if base_kind is not None and base_kind != seen[name]:
                    warnings.warn(
                        "%s: %r overrides a base constraint but changes its kind "
                        "(%s -> %s)" % (cls.__qualname__, name, base_kind,
                                        seen[name]), stacklevel=3)
                continue
            # parse_constraint raises ConstraintParseError if the source is
            # unavailable (REPL/exec/python -c) — a hard failure, because a
            # dropped constraint would silently randomize fields unconstrained.
            prog = parse_constraint(name, member, marker)
            seen[name] = prog.kind
            if prog.kind == "fixed":
                fixed.append(prog)
            else:
                generic[prog.name] = prog
    return fixed, generic


def _safe_kind(name, member, marker):
    """Effective kind of a (possibly shadowed) constraint def, or None if its
    source is unavailable — used only for the override kind-change warning, so a
    base whose source can't be read is simply skipped rather than failing."""
    try:
        return parse_constraint(name, member, marker).kind
    except ConstraintParseError:
        return None


# Statement kinds that have a boolean value (may appear in a generic body that is
# referenced in boolean position). Non-boolean items (soft/dist/solve_order/foreach)
# are rejected in boolean position (design O2, strict v1).
_BOOLEAN_OK_STMT = (_ir.IRConstraintExpr, _ir.IRIfElse, _ir.IRImplies,
                    _ir.IRUnique, _ir.IRConstraintRef)


def _refs_in_expr(e):
    """Yield IRConstraintRef nodes appearing in expression position within ``e``."""
    if e is None:
        return
    if isinstance(e, _ir.IRConstraintRef):
        yield e
        for a in e.args:
            yield from _refs_in_expr(a)
    elif isinstance(e, _ir.IRBin):
        yield from _refs_in_expr(e.lhs)
        yield from _refs_in_expr(e.rhs)
    elif isinstance(e, _ir.IRUnary):
        yield from _refs_in_expr(e.operand)
    elif isinstance(e, _ir.IRInside):
        yield from _refs_in_expr(e.lhs)
        for r in e.ranges:
            yield from _refs_in_expr(r.lo)
            yield from _refs_in_expr(r.hi)
    elif isinstance(e, _ir.IRIndex):
        yield from _refs_in_expr(e.base)
        yield from _refs_in_expr(e.index)
    elif isinstance(e, _ir.IRPartSelect):
        yield from _refs_in_expr(e.base)
        yield from _refs_in_expr(e.upper)
        yield from _refs_in_expr(e.lower)
    elif isinstance(e, _ir.IRAttr):
        yield from _refs_in_expr(e.base)


def _walk_refs(stmts):
    """Yield ``(ref, context)`` for every IRConstraintRef in ``stmts``; context is
    ``"stmt"`` (bare reference) or ``"expr"`` (boolean/value position)."""
    for s in stmts:
        if isinstance(s, _ir.IRConstraintRef):
            yield (s, "stmt")
            for a in s.args:
                for r in _refs_in_expr(a):
                    yield (r, "expr")
        elif isinstance(s, _ir.IRConstraintExpr):
            for r in _refs_in_expr(s.expr):
                yield (r, "expr")
        elif isinstance(s, _ir.IRIfElse):
            for r in _refs_in_expr(s.cond):
                yield (r, "expr")
            yield from _walk_refs(s.true_body)
            if s.false_body:
                yield from _walk_refs(s.false_body)
        elif isinstance(s, _ir.IRImplies):
            for r in _refs_in_expr(s.cond):
                yield (r, "expr")
            yield from _walk_refs(s.body)
        elif isinstance(s, _ir.IRSoft):
            for r in _refs_in_expr(s.expr):
                yield (r, "expr")
        elif isinstance(s, _ir.IRUnique):
            for t in s.terms:
                for r in _refs_in_expr(t):
                    yield (r, "expr")
        elif isinstance(s, _ir.IRForeach):
            yield from _walk_refs(s.body)
        elif isinstance(s, _ir.IRDist):
            for r in _refs_in_expr(s.lhs):
                yield (r, "expr")
            for w in s.weights:
                for r in _refs_in_expr(w.weight):
                    yield (r, "expr")
        # IRSolveOrder references fields only.


def _program_refs(prog):
    if prog.kind == "value":
        return [(r, "expr") for r in _refs_in_expr(prog.ret)]
    return list(_walk_refs(prog.stmts))


def _validate_refs(cls_name, fixed, generic, field_names):
    """Decoration-time validation of all generic-constraint references: resolve
    names, check arity and context, enforce the O2 boolean-body rule, and reject
    reference cycles. Raises TypeError with a source line on any violation."""
    fixed_names = {p.name for p in fixed}

    for owner in list(fixed) + list(generic.values()):
        for ref, ctxk in _program_refs(owner):
            referent = generic.get(ref.name)
            if referent is None:
                if ref.name in fixed_names:
                    raise TypeError(
                        "%s: constraint %r references %r, which is a *fixed* "
                        "constraint and cannot be referenced; mark %r with "
                        "@vdc.constraint.generic (line %d)"
                        % (cls_name, owner.name, ref.name, ref.name, ref.lineno))
                if ref.name in field_names:
                    raise TypeError(
                        "%s: constraint %r references %r, which is a field, not a "
                        "constraint (line %d)"
                        % (cls_name, owner.name, ref.name, ref.lineno))
                raise TypeError(
                    "%s: constraint %r references unknown generic constraint %r "
                    "(line %d)" % (cls_name, owner.name, ref.name, ref.lineno))
            try:
                _ir.bind_actuals(referent.name, referent.params,
                                 referent.param_defaults, ref.args, ref.kwargs)
            except ValueError as e:
                raise TypeError("%s: %s (in %r, line %d)"
                                % (cls_name, e, owner.name, ref.lineno))
            if ctxk == "stmt" and referent.kind == "value":
                raise TypeError(
                    "%s: value generic %r cannot be referenced as a statement "
                    "(in %r, line %d)"
                    % (cls_name, referent.name, owner.name, ref.lineno))
            if ctxk == "expr" and referent.kind == "generic":
                if any(not isinstance(s, _BOOLEAN_OK_STMT) for s in referent.stmts):
                    raise TypeError(
                        "%s: generic %r is used as a boolean term (in %r, line %d) "
                        "but its body contains a non-boolean item "
                        "(soft/dist/solve_order/foreach); reference it as a "
                        "statement instead"
                        % (cls_name, referent.name, owner.name, ref.lineno))

    _detect_ref_cycles(cls_name, generic)


def _detect_ref_cycles(cls_name, generic):
    edges = {}
    for p in generic.values():
        edges[p.name] = {r.name for r, _c in _program_refs(p) if r.name in generic}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in edges}
    stack = []

    def dfs(n):
        color[n] = GRAY
        stack.append(n)
        for m in edges.get(n, ()):
            if color.get(m, BLACK) == GRAY:
                cyc = stack[stack.index(m):] + [m]
                raise TypeError("%s: cyclic generic-constraint reference: %s"
                                % (cls_name, " -> ".join(cyc)))
            if color.get(m, BLACK) == WHITE:
                dfs(m)
        stack.pop()
        color[n] = BLACK

    for n in list(edges):
        if color[n] == WHITE:
            dfs(n)


def _is_rand_class(ann):
    """True if ``ann`` is a class deriving from ``RandClass`` (a nested composite).
    Imported lazily to avoid an import cycle (rand_class -> solve_view -> type_model)."""
    from .rand_class import RandClass
    return isinstance(ann, type) and issubclass(ann, RandClass)


def _type_model_of(cls):
    """Return cls._vsc_type_model, building+caching it lazily if absent."""
    tm = cls.__dict__.get("_vsc_type_model")
    if tm is None:
        tm = build_type_model(cls)
        cls._vsc_type_model = tm
    return tm


def build_type_model(cls):
    """Build (and return) the :class:`TypeModel` for a dataclass ``RandClass``."""
    hints = typing.get_type_hints(cls, include_extras=True)
    fields = []
    for f in dataclasses.fields(cls):
        meta = get_field_meta(f)
        ann = hints.get(f.name)
        if _is_rand_class(ann):
            # Nested composite: a field typed as another RandClass. rand-ness comes
            # from the field factory (vdc.rand() -> rand, vdc.field()/bare -> not).
            fields.append(FieldDecl(
                f.name, 0, False,
                is_rand=(meta.is_rand if meta is not None else False),
                rand_kind=(meta.role if (meta is not None and meta.is_rand) else ""),
                role=(meta.role if meta is not None else ""),
                is_composite=True, comp_cls=ann))
            continue
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
            if _is_rand_class(elem_ann):
                # Array of composites: list[Sub] where Sub is a RandClass.
                fields.append(_composite_array_decl(f.name, meta, elem_ann))
            elif isinstance(elem_ann, EnumMeta):
                # Array of enums: list[MyEnum]. Elements are EnumFieldModels
                # constrained to the enum's values and written back as members.
                fields.append(_enum_array_decl(f.name, meta, elem_ann))
            else:
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

    # A subclass in the hierarchy that adds vdc fields but was not decorated with
    # @vdc.dataclass leaves its ``vdc.rand()``/``field()`` spec as a raw class
    # attribute (a dataclasses.Field): the @dataclass machinery never ran on that
    # level, so the annotation never became a solver field. A constraint that
    # references it would fail deep in lowering with a cryptic "unknown field".
    # Catch it here with an actionable message. (A decorated level instead holds
    # the field's *default value* — never the Field object — at this attribute.)
    field_names = {f.name for f in fields}
    for klass in cls.__mro__:
        for aname, aval in vars(klass).items():
            if (isinstance(aval, dataclasses.Field)
                    and META_KEY in getattr(aval, "metadata", {})
                    and aname not in field_names):
                raise TypeError(
                    "%s: field %r declared on %s never became a solver field — "
                    "decorate %s with @vdc.dataclass (every RandClass level that "
                    "adds fields must be decorated)."
                    % (cls.__qualname__, aname, klass.__qualname__,
                       klass.__qualname__))

    constraints, generic_constraints = _collect_constraints(cls)

    # A constraint method and a field cannot share a name: the method would shadow
    # the field's dataclass default and corrupt both. Catch it with a clear error
    # rather than a downstream TypeError.
    for prog in list(constraints) + list(generic_constraints.values()):
        if prog.name in field_names:
            raise TypeError(
                "%s: constraint method %r collides with a field of the same name; "
                "rename the constraint (e.g. %r)"
                % (cls.__qualname__, prog.name, prog.name + "_c"))

    # Resolve + validate all generic-constraint references at decoration time.
    _validate_refs(cls.__qualname__, constraints, generic_constraints, field_names)

    return TypeModel(cls.__qualname__, fields, constraints, generic_constraints)
