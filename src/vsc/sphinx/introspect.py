"""
Introspection for documentation: pyvsc classes -> plain description objects.

Reads what ``@vdc.dataclass`` already computed and cached on the class
(``_vsc_type_model``, ``_vsc_cg_type_model``), plus the class source for the
text a reader wants to see (constraint bodies, lambda expressions, comments on
bins). Nothing here imports Sphinx, and nothing instantiates the class; the
opt-in elaboration that does is in ``elaborate.py``.

See ``doc/notes/sphinx_extension_design.md`` §5.1.
"""
import ast
import dataclasses
import functools
import inspect
import io
import textwrap
import tokenize
import typing
from dataclasses import dataclass
from enum import Enum, EnumMeta
from typing import Any, Optional, Tuple

from vsc.dc import constraint_ir as _ir
from vsc.dc.coverage.covergroup import Covergroup
from vsc.dc.coverage.descriptors import (Coverpoint, _BinsofAnd, _BinsofNot,
                                         _BinsofOr, _BinsofTerm)
from vsc.dc.fields import get_field_meta
from vsc.dc.rand_class import RandClass
from vsc.dc.type_model import CONSTRAINT_ATTR, _type_model_of
from vsc.dc.types import width_of


# --- Description objects ----------------------------------------------------


@dataclass(frozen=True)
class FieldDesc:
    """One dataclass field of a rand class or covergroup."""
    name: str
    owner: type                     # class whose body declares the field
    type_str: str                   # "u4", "Op", "u8[4]", "Sub[]", "int"
    type_ref: Optional[str]         # dotted name of a class to link (enum/composite)
    kind: str                       # rand | randc | state | cg_arg | sample_arg
    opaque: bool = False            # plain Python state the solver ignores
    domain: Optional[str] = None    # "1..1000", "0..9 (w=3), 10..99 (w=1)"
    size: Optional[str] = None      # "8", "random", "random, <= 16"
    default: Optional[str] = None
    soft: Optional[str] = None
    constrained_by: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintDesc:
    """One constraint method (dataclass or classic)."""
    name: str
    owner: type                     # class whose body defines the constraint
    kind: str                       # fixed | generic | value | dynamic (classic)
    params: Tuple[Tuple[str, Optional[str]], ...] = ()   # (name, default repr)
    doc: Optional[str] = None
    source: Optional[str] = None    # dedented body, docstring removed
    lineno: Optional[int] = None    # line of the def
    filename: Optional[str] = None
    fields_read: Optional[Tuple[str, ...]] = None   # None: unknown (classic)
    generics_used: Tuple[str, ...] = ()
    used_by: Tuple[str, ...] = ()
    overrides: Optional[type] = None   # base class whose same-named constraint this replaces

    @property
    def signature(self):
        """``(n, lo=0)`` for a constraint that takes parameters, else ``""``."""
        if not self.params and self.kind in ("fixed", "dynamic"):
            return ""
        return "(%s)" % ", ".join(
            n if d is None else "%s=%s" % (n, d) for n, d in self.params)


@dataclass(frozen=True)
class BinDesc:
    name: str
    kind: str                       # bin | bin_array | wildcard_bin | wildcard_bin_array
    values: str                     # "0, 1", "0..255", "'0b1x0'"
    count: Optional[int] = None     # number of bins this spec makes; None: unknown
    doc: Optional[str] = None


@dataclass(frozen=True)
class CoverpointDesc:
    name: str
    owner: type
    push: bool
    type_str: str                   # sampled type: "u8", "Op"
    type_ref: Optional[str]
    ref_src: Optional[str] = None   # pull: source of the ref= lambda body
    iff_src: Optional[str] = None
    bins: Tuple[BinDesc, ...] = ()
    auto_bins: Optional[str] = None  # set when bins are automatic
    ignore: Tuple[BinDesc, ...] = ()
    illegal: Tuple[BinDesc, ...] = ()
    options: Tuple[Tuple[str, Any], ...] = ()
    sample_index: Optional[int] = None   # position among the sample() formals
    crossed_by: Tuple[str, ...] = ()
    enum_names: Optional[int] = None     # members of the sampled enum
    n_bins: Optional[int] = None         # elaborated: bins actually built


@dataclass(frozen=True)
class CrossSelDesc:
    name: str
    expr: str                       # "binsof(src).intersect([0..63]) & ..."
    doc: Optional[str] = None


@dataclass(frozen=True)
class CrossDesc:
    name: str
    owner: type
    components: Tuple[str, ...]     # coverpoint (or cross) names
    ignore: Tuple[CrossSelDesc, ...] = ()
    illegal: Tuple[CrossSelDesc, ...] = ()
    options: Tuple[Tuple[str, Any], ...] = ()
    crossed_by: Tuple[str, ...] = ()
    # Elaborated: cross bins, and how many of them are ignored / illegal.
    n_bins: Optional[int] = None
    n_ignore: Optional[int] = None
    n_illegal: Optional[int] = None


@dataclass(frozen=True)
class RandClassDesc:
    cls: type
    fields: Tuple[FieldDesc, ...]
    constraints: Tuple[ConstraintDesc, ...]     # fixed (classic: fixed + dynamic)
    generics: Tuple[ConstraintDesc, ...]        # generic and value
    classic: bool = False
    instantiated: bool = False                  # classic fields read from an instance

    def member_names(self):
        return ([f.name for f in self.fields]
                + [c.name for c in self.constraints + self.generics])


@dataclass(frozen=True)
class CovergroupDesc:
    cls: type
    fields: Tuple[FieldDesc, ...]               # cg_arg / sample_arg / state
    coverpoints: Tuple[CoverpointDesc, ...]
    crosses: Tuple[CrossDesc, ...]
    # The synthesized sample() formals as (name, type_str, type_ref); None when
    # the class defines its own sample().
    sample: Optional[Tuple[Tuple[str, str, Optional[str]], ...]] = None
    classic: bool = False
    elaborated: bool = False                    # counts read from the runtime model

    def member_names(self):
        names = ([f.name for f in self.fields]
                 + [c.name for c in self.coverpoints]
                 + [x.name for x in self.crosses])
        if self.sample is not None:
            names.append("sample")
        return names


# --- Detection --------------------------------------------------------------


def is_randclass(obj):
    """True for a ``@vdc.dataclass`` ``RandClass`` subclass."""
    if not (isinstance(obj, type) and issubclass(obj, RandClass)
            and obj is not RandClass):
        return False
    try:
        _type_model_of(obj)
    except Exception:
        return False
    return True


def is_covergroup(obj):
    """True for a ``@vdc.dataclass`` ``Covergroup`` subclass."""
    return (isinstance(obj, type) and issubclass(obj, Covergroup)
            and "_vsc_cg_type_model" in obj.__dict__)


def classic_user_class(obj):
    """For a classic ``@vsc.randobj`` / ``@vsc.covergroup`` class (the
    interposer the decorator returns), the user's class; else None."""
    if not isinstance(obj, type):
        return None
    mro = obj.__mro__
    for i, k in enumerate(mro[:-1]):
        if k.__name__ in ("randobj_interposer", "covergroup_interposer"):
            return mro[i + 1]
    return None


def is_classic_randobj(obj):
    user = classic_user_class(obj)
    return user is not None and any(
        k.__name__ == "randobj_interposer" for k in obj.__mro__)


def is_classic_covergroup(obj):
    user = classic_user_class(obj)
    return user is not None and any(
        k.__name__ == "covergroup_interposer" for k in obj.__mro__)


def describe_classic_covergroup(cls):
    """A classic ``@vsc.covergroup`` without instantiating it: nothing but the
    class (coverpoints are created in ``__init__``; see
    ``elaborate.instantiate_classic_covergroup``)."""
    return CovergroupDesc(cls, (), (), (), None, classic=True)


# --- Rand classes -----------------------------------------------------------


def describe_randclass(cls):
    """Describe a ``@vdc.dataclass`` rand class."""
    tm = _type_model_of(cls)
    hints = _type_hints(cls)
    dc_fields = {f.name: f for f in dataclasses.fields(cls)}

    progs = list(tm.constraints) + list(tm.generic_constraints.values())
    field_names = [d.name for d in tm.fields]
    composite = {d.name for d in tm.fields if d.is_composite}

    reads = {}
    readers = {n: [] for n in field_names}
    refs = {}
    used_by = {}
    for p in progs:
        names = _display_reads(_ir.fields_read(p), composite)
        reads[p.name] = names
        for n in names:
            head = n.split(".")[0]
            if head in readers and p.name not in readers[head]:
                readers[head].append(p.name)
        refs[p.name] = _ir.refs_used(p)
        for r in refs[p.name]:
            used_by.setdefault(r, []).append(p.name)

    fields = []
    for d in tm.fields:
        f = dc_fields.get(d.name)
        fields.append(_field_desc(cls, d.name, f, hints.get(d.name), decl=d,
                                  constrained_by=readers.get(d.name, ())))

    def cdesc(p):
        owner, func, overrides = _constraint_owner(cls, p.name)
        return _constraint_desc(
            p.name, owner, p.kind, func, overrides,
            fields_read=tuple(reads[p.name]),
            generics_used=tuple(refs[p.name]),
            used_by=tuple(used_by.get(p.name, ())))

    fixed = [cdesc(p) for p in tm.constraints]
    generics = [cdesc(p) for p in tm.generic_constraints.values()]
    # Declaration order (bases first) rather than dict order.
    fixed.sort(key=_decl_key)
    generics.sort(key=_decl_key)
    return RandClassDesc(cls, tuple(fields), tuple(fixed), tuple(generics))


def describe_classic_randobj(cls):
    """Describe a classic ``@vsc.randobj`` class. Only constraints are visible
    without running the constructor: fields are created in ``__init__``."""
    from vsc.constraints import constraint_t, dynamic_constraint_t
    user = classic_user_class(cls) or cls
    seen = set()
    out = []
    for klass in user.__mro__:
        if klass is object or klass.__module__.startswith("vsc."):
            continue
        for name, member in vars(klass).items():
            if name in seen:
                continue
            if isinstance(member, (constraint_t, dynamic_constraint_t)):
                seen.add(name)
                kind = "dynamic" if isinstance(member, dynamic_constraint_t) \
                    else "fixed"
                overrides = None
                for base in klass.__mro__[1:]:
                    if isinstance(base.__dict__.get(name),
                                  (constraint_t, dynamic_constraint_t)):
                        overrides = base
                        break
                # The user's class is documented as the decorated class.
                owner = cls if klass is user else klass
                out.append(_constraint_desc(name, owner, kind, member.c,
                                            overrides, fields_read=None))
    out.sort(key=_decl_key)
    return RandClassDesc(cls, (), tuple(out), (), classic=True)


def _decl_key(c):
    return (len(c.owner.__mro__) if c.owner else 0, c.filename or "",
            c.lineno or 0)


def _display_reads(paths, composite):
    """Field paths -> display names: ``sub.x`` for a composite member, else the
    top-level field (``arr`` for ``arr.size``)."""
    out = []
    for p in paths:
        n = ".".join(p[:2]) if (p[0] in composite and len(p) > 1) else p[0]
        if n not in out:
            out.append(n)
    return out


def _constraint_owner(cls, name):
    """(defining class, function, overridden base class or None)."""
    owner = func = overrides = None
    for klass in cls.__mro__:
        m = klass.__dict__.get(name)
        if m is not None and getattr(m, CONSTRAINT_ATTR, None):
            if owner is None:
                owner, func = klass, m
            else:
                overrides = klass
                break
    return owner, func, overrides


def _constraint_desc(name, owner, kind, func, overrides, fields_read=None,
                     generics_used=(), used_by=()):
    params = ()
    doc = source = filename = lineno = None
    if func is not None:
        try:
            sig = inspect.signature(func)
            ps = list(sig.parameters.values())[1:]   # drop self
            params = tuple(
                (p.name, None if p.default is inspect.Parameter.empty
                 else repr(p.default)) for p in ps)
        except (TypeError, ValueError):
            pass
        # Not inspect.getdoc: an overriding constraint does not inherit the
        # base's docstring, since its body (its meaning) differs.
        doc = inspect.cleandoc(func.__doc__) if func.__doc__ else None
        source, lineno = _function_body(func)
        try:
            filename = inspect.getsourcefile(func)
        except TypeError:
            pass
    return ConstraintDesc(
        name=name, owner=owner, kind=kind, params=params, doc=doc,
        source=source, lineno=lineno, filename=filename,
        fields_read=fields_read, generics_used=tuple(generics_used),
        used_by=tuple(used_by), overrides=overrides)


def _function_body(func):
    """(body source, def line): the function body as written, dedented, with
    the decorator, ``def`` line and docstring removed. Comments directly above
    the first statement are kept."""
    try:
        lines, start = inspect.getsourcelines(func)
    except (OSError, TypeError):
        return None, None
    src = textwrap.dedent("".join(lines))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None, start
    fdef = next((n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if fdef is None or not fdef.body:
        return None, start
    src_lines = src.splitlines()
    body = fdef.body
    def_line = fdef.lineno           # 1-based, after decorators
    if _is_docstring(body[0]):
        first = body[0].end_lineno + 1
        body = body[1:]
        if not body:
            return "", start + def_line - 1
    else:
        first = body[0].lineno
        # Keep comment lines immediately above the first statement.
        while first - 1 > def_line and \
                src_lines[first - 2].strip().startswith("#"):
            first -= 1
    last = body[-1].end_lineno
    if first == def_line:            # one-liner: def c(self): self.a < 4
        seg = ast.get_source_segment(src, body[0]) or ""
        return seg.strip(), start + def_line - 1
    text = "\n".join(src_lines[first - 1:last])
    return textwrap.dedent(text).strip("\n"), start + def_line - 1


def _is_docstring(node):
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


# --- Fields -----------------------------------------------------------------


def _type_hints(cls):
    try:
        return typing.get_type_hints(cls, include_extras=True)
    except Exception:
        return {}


def _field_owner(cls, name):
    owner = cls
    for klass in reversed(cls.__mro__):
        if name in klass.__dict__.get("__annotations__", {}):
            owner = klass
    return owner


def _qualname(t):
    return "%s.%s" % (t.__module__, t.__qualname__)


def _ann_str(ann):
    if ann is None:
        return ""
    if isinstance(ann, type):
        return ann.__qualname__
    return str(ann).replace("typing.", "")


def _scalar_str(ann, bits, signed, explicit_width):
    """``u4`` / ``s16`` for a width-typed field; the annotation as written for
    a bare ``int`` / ``bool`` with no width given."""
    w = width_of(ann)
    if w is None and not explicit_width:
        return _ann_str(ann) or "int"
    return "%s%d" % ("s" if signed else "u", bits)


def _value_str(v):
    if isinstance(v, Enum):
        return "%s.%s" % (type(v).__name__, v.name)
    return repr(v)


def _domain_str(dom):
    if dom is None or not dom.ranges:
        return None
    parts = []
    for i, (lo, hi) in enumerate(dom.ranges):
        s = str(lo) if lo == hi else "%d..%d" % (lo, hi)
        if dom.weights is not None:
            s += " (w=%s)" % dom.weights[i]
        parts.append(s)
    return ", ".join(parts)


def _field_desc(cls, name, f, ann, decl=None, constrained_by=()):
    meta = get_field_meta(f) if f is not None else None
    owner = _field_owner(cls, name)
    type_ref = None
    opaque = False
    size = None

    if decl is not None:
        role = decl.rand_kind or decl.role or ""
        opaque = decl.is_opaque
        explicit = meta is not None and meta.width is not None
        if decl.is_composite:
            type_str, type_ref = decl.comp_cls.__name__, _qualname(decl.comp_cls)
        elif decl.enum_cls is not None and not decl.is_array:
            type_str, type_ref = decl.enum_cls.__name__, _qualname(decl.enum_cls)
        elif decl.is_array:
            if decl.elem_comp_cls is not None:
                elem, type_ref = (decl.elem_comp_cls.__name__,
                                  _qualname(decl.elem_comp_cls))
            elif decl.enum_cls is not None:
                elem, type_ref = decl.enum_cls.__name__, _qualname(decl.enum_cls)
            else:
                elem_ann = typing.get_args(ann)[0] if typing.get_args(ann) else None
                elem = _scalar_str(elem_ann, decl.bits, decl.signed, explicit)
            if decl.size is not None:
                type_str = "%s[%d]" % (elem, decl.size)
            else:
                type_str = "%s[]" % elem
                if decl.is_rand_sz:
                    size = "random" if decl.max_size is None else \
                        "random, <= %d" % decl.max_size
        elif opaque:
            type_str = _ann_str(ann)
        else:
            type_str = _scalar_str(ann, decl.bits, decl.signed, explicit)
        domain = _domain_str(decl.domain)
        soft = None if decl.soft is None else _value_str(decl.soft)
    else:
        # Covergroup fields: no TypeModel; read the metadata directly.
        role = meta.role if meta is not None else ""
        domain = soft = None
        if isinstance(ann, EnumMeta):
            type_str, type_ref = ann.__name__, _qualname(ann)
        elif width_of(ann) is not None or (meta is not None and meta.width):
            w = width_of(ann) or (32, True)
            bits = meta.width if (meta is not None and meta.width) else w[0]
            signed = meta.signed if (meta is not None and meta.signed is not None) \
                else w[1]
            type_str = "%s%d" % ("s" if signed else "u", bits)
        else:
            type_str = _ann_str(ann)

    kind = role if role in ("rand", "randc", "cg_arg", "sample_arg") else "state"

    default = None
    if f is not None and f.default is not dataclasses.MISSING \
            and decl is not None and not decl.is_array and not decl.is_composite:
        default = _value_str(f.default)
    elif f is not None and decl is None and f.default is not dataclasses.MISSING:
        default = _value_str(f.default)

    return FieldDesc(name=name, owner=owner, type_str=type_str, type_ref=type_ref,
                     kind=kind, opaque=opaque, domain=domain, size=size,
                     default=default, soft=soft,
                     constrained_by=tuple(constrained_by))


# --- Covergroups ------------------------------------------------------------


def describe_covergroup(cls):
    """Describe a ``@vdc.dataclass`` covergroup."""
    tm = cls._vsc_cg_type_model
    hints = _type_hints(cls)

    fields = tuple(_field_desc(cls, f.name, f, hints.get(f.name))
                   for f in dataclasses.fields(cls))

    formal_index = {name: i for i, (_k, name) in enumerate(tm.sample_formals)}
    names = {d.name for d in tm.coverpoints} | {c.name for c in tm.crosses}
    components = {c.name: _cross_components(c, names) for c in tm.crosses}
    crossed_by = {}
    for cname, comps in components.items():
        for comp in comps:
            crossed_by.setdefault(comp, []).append(cname)

    cps = []
    for d in tm.coverpoints:
        owner = _descriptor_owner(cls, d.name, d)
        src = _ClassSource.of(owner)
        cps.append(_coverpoint_desc(d, owner, src, formal_index.get(d.name),
                                    tuple(crossed_by.get(d.name, ()))))

    crs = []
    for c in tm.crosses:
        owner = _descriptor_owner(cls, c.name, c)
        src = _ClassSource.of(owner)
        crs.append(CrossDesc(
            name=c.name, owner=owner, components=components[c.name],
            ignore=_cross_selects(c.ignore_bins, src, c.name, "ignore_bins",
                                  names),
            illegal=_cross_selects(c.illegal_bins, src, c.name, "illegal_bins",
                                   names),
            options=tuple((c.options or {}).items()),
            crossed_by=tuple(crossed_by.get(c.name, ()))))

    sample = None
    if _is_synth_sample(cls):
        sample = tuple(_sample_formal(n, ann) for n, ann in tm.sample_param_spec)

    return CovergroupDesc(cls, fields, tuple(cps), tuple(crs), sample)


def _is_synth_sample(cls):
    """True if ``cls.sample`` is the one ``@vdc.dataclass`` synthesized (for this
    class or a decorated base), not a user override."""
    for k in cls.__mro__:
        s = k.__dict__.get("sample")
        if s is None:
            continue
        if k is Covergroup:
            return True     # the generic binder: no formals beyond **kwargs
        return getattr(s, "__signature__", None) is not None and \
            getattr(s, "__qualname__", "") == "%s.sample" % k.__qualname__ and \
            s.__code__.co_filename == "<string>"
    return False


def _sample_formal(name, ann):
    if isinstance(ann, type) and issubclass(ann, Enum):
        return (name, ann.__name__, _qualname(ann))
    return (name, _ann_str(ann), None)


def _descriptor_owner(cls, name, desc):
    for klass in cls.__mro__:
        if klass.__dict__.get(name) is desc:
            return klass
    return cls


def _coverpoint_desc(d, owner, src, sample_index, crossed_by):
    if d.enum_cls is not None:
        type_str, type_ref = d.enum_cls.__name__, _qualname(d.enum_cls)
    else:
        type_str, type_ref = "%s%d" % ("s" if d.signed else "u", d.width or 32), None

    ref_src = iff_src = None
    if src is not None:
        node = src.call_arg(d.name, 0, "ref")
        ref_src = src.lambda_src(node)
        iff_src = src.lambda_src(src.call_arg(d.name, None, "iff"))

    auto = None
    if not d.bins:
        options = d.options or {}
        if d.enum_cls is not None:
            auto = "one bin per member of %s" % d.enum_cls.__name__
        else:
            w = d.width or 32
            nvals = 1 << w
            n = min(nvals, options.get("auto_bin_max", 64))
            lo, hi = ((-(nvals >> 1), (nvals >> 1) - 1) if d.signed
                      else (0, nvals - 1))
            auto = "%d bin%s over %d..%d" % (n, "" if n == 1 else "s", lo, hi)

    return CoverpointDesc(
        enum_names=len(d.enum_cls) if d.enum_cls is not None else None,
        name=d.name, owner=owner, push=d.is_push, type_str=type_str,
        type_ref=type_ref, ref_src=ref_src, iff_src=iff_src,
        bins=_bin_descs(d.bins, src, d.name, "bins"),
        auto_bins=auto,
        ignore=_bin_descs(d.ignore_bins, src, d.name, "ignore_bins"),
        illegal=_bin_descs(d.illegal_bins, src, d.name, "illegal_bins"),
        options=tuple((d.options or {}).items()),
        sample_index=sample_index if d.is_push else None,
        crossed_by=crossed_by)


def _bin_descs(bins, src, attr, kw):
    if not bins:
        return ()
    comments = src.dict_comments(attr, kw) if src is not None else {}
    return tuple(_bin_desc(name, spec, comments.get(name))
                 for name, spec in bins.items())


def _ranges_of(args):
    """Bin-spec arguments -> list of (lo, hi), for the spellings bin/bin_array
    accept: ``1, (2, 4), 8`` or a single list of those."""
    if len(args) == 1 and isinstance(args[0], (list, tuple)) and args[0] \
            and isinstance(args[0][0], (list, tuple)):
        args = args[0]
    out = []
    for a in args:
        if isinstance(a, (list, tuple)):
            if len(a) == 2:
                out.append((a[0], a[1]))
            elif len(a) == 1:
                out.append((a[0], a[0]))
        elif isinstance(a, int):
            out.append((a, a))
    return out


def _ranges_str(ranges):
    return ", ".join(str(lo) if lo == hi else "%d..%d" % (lo, hi)
                     for lo, hi in ranges)


def _bin_desc(name, spec, comment):
    from vsc.coverage import bin as _bin, bin_array, wildcard_bin, \
        wildcard_bin_array
    doc = getattr(spec, "doc", None) or comment
    args = getattr(spec, "spec_args", None)
    if isinstance(spec, _bin):
        r = _ranges_of(args if args is not None else spec.range_l)
        return BinDesc(name, "bin", _ranges_str(r), 1, doc)
    if isinstance(spec, bin_array):
        r = _ranges_of(args or ())
        nvals = sum(hi - lo + 1 for lo, hi in r)
        count = spec.nbins if spec.nbins > 0 else nvals
        return BinDesc(name, "bin_array", _ranges_str(r), count, doc)
    if isinstance(spec, (wildcard_bin, wildcard_bin_array)):
        vals = ", ".join(_wildcard_str(a) for a in (args or ()))
        if isinstance(spec, wildcard_bin):
            return BinDesc(name, "wildcard_bin", vals, 1, doc)
        count = spec.nbins if spec.nbins > 0 else None
        return BinDesc(name, "wildcard_bin_array", vals, count, doc)
    return BinDesc(name, type(spec).__name__, repr(spec), None, doc)


def _wildcard_str(a):
    if isinstance(a, str):
        return repr(a)
    if isinstance(a, (list, tuple)) and len(a) == 2:
        return "(0x%x, mask 0x%x)" % (a[0], a[1])
    return repr(a)


# --- Crosses: probing the lambdas -------------------------------------------


class _Probe:
    """Stands in for the covergroup instance when calling a cross's lambdas:
    each coverpoint / cross attribute is a stand-in coverpoint that knows its
    name. Exact for any target form the runtime accepts, without parsing the
    lambda. Any other attribute (a cg_arg, a sample_arg) raises, so a
    selection that reads one is shown as written."""

    def __init__(self, names=None):
        self._names = names

    def __getattr__(self, name):
        if name.startswith("_") or (self._names is not None
                                    and name not in self._names):
            raise AttributeError(name)
        cp = Coverpoint.__new__(Coverpoint)
        cp._name = name
        cp._model = None
        cp._enum_cls = None
        cp._staged = 0
        return cp


def _cross_components(c, names=None):
    out = []
    for t in c.targets:
        try:
            rt = t(_Probe(names))
            out.append(rt._name)
        except Exception:
            out.append("?")
    return tuple(out)


def _cross_selects(selects, src, attr, kw, names=None):
    if not selects:
        return ()
    comments = src.dict_comments(attr, kw) if src is not None else {}
    lambdas = src.dict_values(attr, kw) if src is not None else {}
    out = []
    for name, sel in selects.items():
        expr = None
        try:
            e = sel(_Probe(names)) if callable(sel) else sel
            expr = binsof_str(e)
        except Exception:
            pass
        if expr is None:
            expr = src.lambda_src(lambdas.get(name)) if src is not None else None
        out.append(CrossSelDesc(name, expr or "?", comments.get(name)))
    return tuple(out)


def binsof_str(e, parent=None):
    """Render a ``binsof`` selection tree as text, parenthesized only where
    ``&`` / ``|`` precedence requires it."""
    if isinstance(e, _BinsofTerm):
        s = "binsof(%s)" % e.cp._name
        if e.values is not None:
            s += ".intersect([%s])" % ", ".join(
                "(%s, %s)" % (v[0], v[1]) if isinstance(v, (list, tuple))
                else str(v) for v in e.values)
        return s
    if isinstance(e, _BinsofAnd):
        return "%s & %s" % (binsof_str(e.lhs, "and"), binsof_str(e.rhs, "and"))
    if isinstance(e, _BinsofOr):
        s = "%s | %s" % (binsof_str(e.lhs, "or"), binsof_str(e.rhs, "or"))
        return "(%s)" % s if parent == "and" else s
    if isinstance(e, _BinsofNot):
        inner = binsof_str(e.operand, "not")
        return "~" + (inner if isinstance(e.operand, _BinsofTerm)
                      else "(%s)" % inner)
    raise TypeError("not a binsof expression: %r" % (e,))


# --- Class source -----------------------------------------------------------


class _ClassSource:
    """The parsed source of one class body: assignments by name, plus every
    comment by line. Used for the text of lambdas and comments on dict entries,
    which the runtime objects do not keep."""

    def __init__(self, cls):
        lines, _start = inspect.getsourcelines(cls)
        self.src = textwrap.dedent("".join(lines))
        tree = ast.parse(self.src)
        cdef = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        self.assigns = {}
        for st in cdef.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) \
                    and st.value is not None:
                self.assigns[st.target.id] = st.value
            elif isinstance(st, ast.Assign):
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        self.assigns[t.id] = st.value
        # Classic classes: ``self.<name> = ...`` in ``__init__``. A class-level
        # assignment of the same name wins.
        self.self_assigns = {}
        for st in cdef.body:
            if isinstance(st, ast.FunctionDef) and st.name == "__init__":
                for n in ast.walk(st):
                    if isinstance(n, ast.Assign):
                        for t in n.targets:
                            if isinstance(t, ast.Attribute) and \
                                    isinstance(t.value, ast.Name) and \
                                    t.value.id == "self":
                                self.self_assigns.setdefault(t.attr, n.value)
        for k, v in self.self_assigns.items():
            self.assigns.setdefault(k, v)
        self.lines = self.src.splitlines()
        self.comments = {}
        try:
            for tok in tokenize.generate_tokens(io.StringIO(self.src).readline):
                if tok.type == tokenize.COMMENT:
                    self.comments[tok.start[0]] = (tok.start[1], tok.string)
        except (tokenize.TokenError, IndentationError):
            pass

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def of(cls):
        try:
            return _ClassSource(cls)
        except Exception:
            return None

    def call_arg(self, name, index, kw):
        node = self.assigns.get(name)
        if not isinstance(node, ast.Call):
            return None
        for k in node.keywords:
            if k.arg == kw:
                return k.value
        if index is not None and len(node.args) > index:
            return node.args[index]
        return None

    def segment(self, node):
        if node is None:
            return None
        s = ast.get_source_segment(self.src, node)
        if s is None:
            return None
        # A multi-line segment keeps the continuation lines' indentation.
        first, *rest = s.splitlines()
        if rest:
            s = "\n".join([first, textwrap.dedent("\n".join(rest))])
        return " ".join(part.strip() for part in s.splitlines())

    def lambda_src(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Lambda):
            return self.segment(node.body)
        return self.segment(node)

    def _entries(self, node):
        """[(key, first line, value node)] of a ``{...}`` or ``dict(...)``."""
        out = []
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.append((k.value, k.lineno, v))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "dict":
            for k in node.keywords:
                if k.arg is not None:
                    out.append((k.arg, k.lineno, k.value))
        return out

    def dict_values(self, name, kw):
        return {k: v for k, _l, v in self._entries(self.call_arg(name, None, kw))}

    def dict_comments(self, name, kw):
        """{key: comment} for the entries of a dict argument: the trailing
        comment on the entry's last line (when no other entry ends on that
        line), else comment-only lines directly above the entry."""
        entries = self._entries(self.call_arg(name, None, kw))
        out = {}
        ends = {}
        for k, _first, v in entries:
            ends.setdefault(v.end_lineno, []).append(k)
        for k, first, v in entries:
            text = None
            c = self.comments.get(v.end_lineno)
            if c is not None and len(ends[v.end_lineno]) == 1 \
                    and c[0] >= v.end_col_offset:
                text = _comment_text(c[1])
            if text is None:
                above = []
                ln = first - 1
                while ln >= 1 and self.lines[ln - 1].strip().startswith("#"):
                    above.insert(0, _comment_text(self.lines[ln - 1].strip()))
                    ln -= 1
                if above:
                    text = " ".join(above)
            if text:
                out[k] = text
        return out


def _comment_text(c):
    c = c.lstrip("#")
    if c.startswith(":"):
        c = c[1:]
    return c.strip()
