"""
CovergroupTypeModel — the per-type, instance-independent elaboration of a
``@vdc.dataclass`` ``Covergroup``: its coverpoint/cross definitions (with bin specs
and resolved widths) and the synthesized sample()-formal list. Built once at
decoration time and cached as ``cls._vsc_cg_type_model``.

This is the *structure* half of the coverage seam (see
``memory/dc-coverage-reuse-sv-model.md``): elaborate once here; the per-instance
runtime (classic CoverpointModel/CovergroupModel tree, for now) is materialized in
``covergroup._build_runtime`` and is the part a flat-count / native collector would
later replace.
"""
import typing
from enum import EnumMeta

from ..fields import get_field_meta
from ..types import width_of
from .descriptors import _CPDescriptor, _CrossDescriptor


class CovergroupTypeModel:
    __slots__ = ("cls_name", "coverpoints", "crosses",
                 "sample_formals", "formal_by_name")

    def __init__(self, cls_name, coverpoints, crosses, sample_formals):
        self.cls_name = cls_name
        self.coverpoints = coverpoints      # ordered list[_CPDescriptor]
        self.crosses = crosses              # ordered list[_CrossDescriptor]
        # sample() formal binding: ordered list of (kind, name); kind in
        # {"cp" (push coverpoint), "arg" (sample_arg field)}.
        self.sample_formals = sample_formals
        self.formal_by_name = {name: (kind, name) for kind, name in sample_formals}

    def __repr__(self):
        return "CovergroupTypeModel(%s, %d cp, %d cross)" % (
            self.cls_name, len(self.coverpoints), len(self.crosses))


def _resolve_cp_type(desc, ann):
    """Resolve a coverpoint's width/signed/enum from its ``Coverpoint[T]``
    annotation (or an explicit ``cp_t=``)."""
    # Explicit cp_t override: an Enum class, or a width-typed alias.
    if desc.cp_t is not None:
        if isinstance(desc.cp_t, EnumMeta):
            desc.enum_cls = desc.cp_t
            desc.width = 32
            return
        w = width_of(desc.cp_t)
        if w is not None:
            desc.width, desc.signed = w[0], bool(w[1])
            return
    args = typing.get_args(ann) if ann is not None else ()
    if args:
        t = args[0]
        if isinstance(t, EnumMeta):
            desc.enum_cls = t
            desc.width = 32
            return
        w = width_of(t)
        if w is not None and w[0] >= 0:
            desc.width, desc.signed = w[0], bool(w[1])
            return
    # No width recoverable: fine only if explicit bins were given (the bins define
    # the structure); default to 32-bit otherwise.
    desc.width = 32


def prepare_covergroup(cls):
    """Resolve coverpoint widths from ``Coverpoint[T]`` annotations, then strip the
    coverpoint/cross attributes from ``__annotations__`` so the dataclass transform
    doesn't treat them as data fields (they stay as class-level descriptors).

    Must run *before* ``dataclasses.dataclass``."""
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except Exception:
        hints = {}
    own = cls.__dict__.get("__annotations__", {})
    for name in list(own):
        attr = cls.__dict__.get(name)
        if isinstance(attr, _CPDescriptor):
            _resolve_cp_type(attr, hints.get(name))
            del own[name]
        elif isinstance(attr, _CrossDescriptor):
            del own[name]


def build_cg_type_model(cls):
    """Collect coverpoint/cross descriptors across the MRO (subclass overrides win
    by name), ordered by declaration, and compute the sample()-formal list."""
    cps = {}
    crs = {}
    for klass in reversed(cls.__mro__):
        for name, attr in vars(klass).items():
            if isinstance(attr, _CPDescriptor):
                cps[name] = attr
            elif isinstance(attr, _CrossDescriptor):
                crs[name] = attr
    coverpoints = sorted(cps.values(), key=lambda d: d.order)
    crosses = sorted(crs.values(), key=lambda d: d.order)

    # Synthesized sample() formals: push coverpoints (declaration order), then
    # sample_arg fields (dataclass field order).
    formals = [("cp", d.name) for d in coverpoints if d.is_push]
    import dataclasses
    for f in dataclasses.fields(cls):
        meta = get_field_meta(f)
        if meta is not None and meta.role == "sample_arg":
            formals.append(("arg", f.name))

    return CovergroupTypeModel(cls.__qualname__, coverpoints, crosses, formals)
