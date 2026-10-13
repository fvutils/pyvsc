"""
Opt-in elaboration: what only the runtime model knows.

- ``elaborate_covergroup``: exact bin counts for a ``@vdc.dataclass``
  covergroup (bins left after ignore / illegal exclusions, automatic bins,
  cross totals). The coverpoint and cross models are built from the class's
  descriptors on a bare instance: the class's ``__init__`` / ``__post_init__``
  do not run and nothing is registered for coverage reporting. The only user
  code run is the cross target and selection lambdas.
- ``instantiate_classic_randobj`` / ``instantiate_classic_covergroup``: a
  classic class creates its fields and coverpoints in ``__init__``, so one
  instance is constructed with no arguments. A covergroup is constructed
  against a scratch coverage registry, so the documentation instance does not
  appear in coverage reports.

Each raises ``ElaborationError`` if the class cannot be elaborated; the caller
falls back to the static description. Nothing here imports Sphinx.

See ``doc/notes/sphinx_extension_design.md`` §6.3, §9 and §15.
"""
import contextlib
import dataclasses

from vsc.impl.coverage_registry import CoverageRegistry

from . import introspect as I


class ElaborationError(Exception):
    """The class could not be elaborated; ``__cause__`` says why."""


@contextlib.contextmanager
def scratch_registry():
    """Route covergroup registration to a throwaway ``CoverageRegistry``."""
    saved = CoverageRegistry._inst
    CoverageRegistry._inst = None
    try:
        yield
    finally:
        CoverageRegistry._inst = saved


def _error(cls, what, e):
    err = ElaborationError("%s %s.%s: %s: %s" % (
        what, cls.__module__, cls.__qualname__, type(e).__name__, e))
    err.__cause__ = e
    return err


# --- Dataclass covergroups --------------------------------------------------


def elaborate_covergroup(cls):
    """The description of a ``@vdc.dataclass`` covergroup with exact counts."""
    desc = I.describe_covergroup(cls)
    try:
        obj = cls.__new__(cls)
        # The selection lambdas may read cg_args; give them their defaults.
        for f in dataclasses.fields(cls):
            if f.default is not dataclasses.MISSING:
                object.__setattr__(obj, f.name, f.default)
            elif f.default_factory is not dataclasses.MISSING:
                object.__setattr__(obj, f.name, f.default_factory())
        with scratch_registry():
            obj._build_models()
        cp_models = {n: cp._model for n, cp in obj._cp_insts.items()}
        x_models = {n: x._model for n, x in obj._cr_insts.items()}
    except Exception as e:
        raise _error(cls, "cannot elaborate covergroup", e) from e
    return apply_models(desc, cp_models, x_models)


def apply_models(desc, cp_models, x_models):
    """``desc`` with the counts read from finalized coverpoint / cross models
    (``{name: CoverpointModel}``, ``{name: CoverpointCrossModel}``)."""
    cps = []
    for cp in desc.coverpoints:
        m = cp_models.get(cp.name)
        if m is None:
            cps.append(cp)
            continue
        counts = {b.name: b.get_n_bins() for b in m.bin_model_l}
        bins = tuple(dataclasses.replace(b, count=counts.get(b.name, 0))
                     for b in cp.bins)
        auto = None if cp.bins else _auto_text(cp, m)
        cps.append(dataclasses.replace(cp, bins=bins, auto_bins=auto,
                                       n_bins=m.get_n_bins()))
    crs = []
    for x in desc.crosses:
        m = x_models.get(x.name)
        if m is None:
            crs.append(x)
            continue
        crs.append(dataclasses.replace(x, n_bins=m.n_bins, n_ignore=m.n_ignore,
                                       n_illegal=m.n_illegal))
    return dataclasses.replace(desc, coverpoints=tuple(cps), crosses=tuple(crs),
                               elaborated=True)


def _auto_text(cp, m):
    """Automatic bins as built: ``64 bins of 4 values over 0..255``, ``3 bins,
    one per member of Op``."""
    n = m.get_n_bins()
    plural = "" if n == 1 else "s"
    if n == 0:
        return "no bins (every value excluded)"
    if cp.enum_names is not None:
        text = "%d bin%s, one per member of %s" % (n, plural, cp.type_str)
        if n < cp.enum_names:
            text += " (%d excluded)" % (cp.enum_names - n)
        return text
    ranges = [m.get_bin_range(i) for i in range(n)]
    sizes = []
    lo = hi = None
    for entries in ranges:
        size = 0
        for e in entries:
            a, b = e if isinstance(e, tuple) else (e, e)
            size += b - a + 1
            lo = a if lo is None else min(lo, a)
            hi = b if hi is None else max(hi, b)
        sizes.append(size)
    if min(sizes) == max(sizes):
        per = "%d value%s" % (sizes[0], "" if sizes[0] == 1 else "s")
    else:
        per = "%d to %d values" % (min(sizes), max(sizes))
    return "%d bin%s of %s over %d..%d" % (n, plural, per, lo, hi)


# --- Classic classes --------------------------------------------------------


def _construct(cls):
    with scratch_registry():
        return cls()


def instantiate_classic_randobj(cls):
    """The description of a classic ``@vsc.randobj`` with the fields one
    instance has."""
    desc = I.describe_classic_randobj(cls)
    try:
        obj = _construct(cls)
        fields = tuple(_classic_fields(cls, obj))
    except Exception as e:
        raise _error(cls, "cannot instantiate", e) from e
    return dataclasses.replace(desc, fields=fields, instantiated=True)


def instantiate_classic_covergroup(cls):
    """The description of a classic ``@vsc.covergroup``: its sampling inputs,
    coverpoints and crosses, with exact counts."""
    from vsc.coverage import coverpoint, cross
    user = I.classic_user_class(cls)
    try:
        obj = _construct(cls)
        cg_i = obj._get_int()
        src = I._ClassSource.of(user)

        names = {}
        for n, v in vars(obj).items():
            names.setdefault(id(v), n)

        sample = tuple((n,) + _classic_type(t)
                       for n, t in zip(cg_i.sample_var_l, cg_i.sample_obj_l))
        fields = tuple(
            I.FieldDesc(name=n, owner=cls, type_str=ts, type_ref=tr,
                        kind="sample_arg")
            for n, ts, tr in sample)

        cp_objs = [b for b in obj.buildable_l if isinstance(b, coverpoint)]
        x_objs = [b for b in obj.buildable_l if isinstance(b, cross)]
        components = {}
        for x in x_objs:
            components[names.get(id(x), x.name)] = tuple(
                names.get(id(t), t.name or "?") for t in x.target_l)
        crossed_by = {}
        for xn, comps in components.items():
            for c in comps:
                crossed_by.setdefault(c, []).append(xn)

        cps, cp_models = [], {}
        for b in cp_objs:
            n = names.get(id(b), b.name)
            cps.append(_classic_coverpoint(n, b, cls, src,
                                           tuple(crossed_by.get(n, ()))))
            cp_models[n] = b.model
        crs, x_models = [], {}
        for x in x_objs:
            n = names.get(id(x), x.name)
            crs.append(I.CrossDesc(
                name=n, owner=cls, components=components[n],
                # Classic selections are predicates over component bins,
                # shown as written.
                ignore=I._cross_selects(x.ignore_bins, src, n, "ignore_bins",
                                        frozenset()),
                crossed_by=tuple(crossed_by.get(n, ()))))
            x_models[n] = x.model
    except Exception as e:
        raise _error(cls, "cannot instantiate", e) from e

    desc = I.CovergroupDesc(cls, fields, tuple(cps), tuple(crs), sample,
                            classic=True)
    return apply_models(desc, cp_models, x_models)


def _classic_type(t):
    """(type_str, type_ref) of a classic field object."""
    from vsc.types import list_t, type_base, type_enum
    if isinstance(t, type_enum):
        e = t.enum_i.e
        return e.__name__, I._qualname(e)
    if isinstance(t, type_base):
        return "%s%d" % ("s" if t.is_signed else "u", t.width), None
    if isinstance(t, list_t):
        elem, ref = _classic_type(t.t)
        if t.is_rand_sz or t.init is not None or t.init_sz <= 0:
            return "%s[]" % elem, ref
        return "%s[%d]" % (elem, t.init_sz), ref
    if hasattr(t, "_int_field_info"):
        k = type(t)
        return k.__name__, I._qualname(k)
    return type(t).__name__, None


def _classic_owner(cls, name):
    """The base-most user class whose ``__init__`` assigns ``self.<name>``
    (``cls`` for the documented class itself, or when unknown)."""
    user = I.classic_user_class(cls)
    seen = set()
    for k in reversed(cls.__mro__):
        u = I.classic_user_class(k)
        if u is None or u in seen:
            continue
        seen.add(u)
        src = I._ClassSource.of(u)
        if src is not None and name in src.self_assigns:
            return cls if u is user else u
    return cls


def _classic_fields(cls, obj):
    from vsc.types import list_t, type_base
    for name, v in vars(obj).items():
        if name.startswith("_"):
            continue
        info = getattr(v, "_int_field_info", None)
        if info is None:
            continue
        type_str, type_ref = _classic_type(v)
        size = None
        if isinstance(v, list_t) and v.is_rand_sz:
            size = "random"
        default = None
        if isinstance(v, type_base) and not hasattr(v, "enum_i"):
            init = getattr(v, "_init_val", 0)
            if init:
                default = repr(init)
        yield I.FieldDesc(
            name=name, owner=_classic_owner(cls, name), type_str=type_str,
            type_ref=type_ref, kind="rand" if info.is_rand else "state",
            size=size, default=default)


def _classic_coverpoint(name, b, cls, src, crossed_by):
    from vsc.types import type_enum
    type_str, type_ref = _classic_type(b.cp_t) if b.cp_t is not None else ("", None)
    enum_names = len(b.cp_t.enum_i.enums) if isinstance(b.cp_t, type_enum) else None
    ref_src = iff_src = None
    if src is not None:
        ref_src = src.lambda_src(src.call_arg(name, 0, "target"))
        iff_src = src.lambda_src(src.call_arg(name, None, "iff"))
    return I.CoverpointDesc(
        name=name, owner=cls, push=False, type_str=type_str, type_ref=type_ref,
        ref_src=ref_src, iff_src=iff_src,
        bins=I._bin_descs(b.bins, src, name, "bins"),
        auto_bins=None,                     # set by apply_models
        ignore=I._bin_descs(b.ignore_bins, src, name, "ignore_bins"),
        illegal=I._bin_descs(b.illegal_bins, src, name, "illegal_bins"),
        crossed_by=crossed_by, enum_names=enum_names)
