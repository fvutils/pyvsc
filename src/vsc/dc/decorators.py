"""
``@vdc.dataclass`` — the single transform decorator, and ``@vdc.constraint`` — the
constraint-method tag.

``@vdc.dataclass`` runs ``dataclasses.dataclass(kw_only=True)`` exactly once, then
dispatches on the capability base class to build and cache the appropriate per-type
model (``TypeModel`` for ``RandClass``; ``CovergroupTypeModel`` for ``Covergroup``,
Phase 3). It is the PEP 681 ``@dataclass_transform`` anchor so type checkers
understand the synthesized ``__init__``.

See ``doc/notes/dataclass_pyvsc_impl_test_doc_plan.md`` §2.3.
"""
import dataclasses
import typing

try:
    from typing import dataclass_transform
except ImportError:  # pragma: no cover - Python < 3.11
    def dataclass_transform(**kwargs):
        def _wrap(o):
            return o
        return _wrap

from .fields import field as _field, rand as _rand, randc as _randc
from .rand_class import RandClass
from .type_model import CONSTRAINT_ATTR, build_type_model


def constraint(func):
    """Tag a method as a constraint. The body is parsed (not executed) once per
    type by the constraint compiler."""
    setattr(func, CONSTRAINT_ATTR, True)
    return func


def _fixup_composite_defaults(cls):
    """A field typed as another ``RandClass`` (a nested composite) needs a
    ``default_factory`` that constructs a fresh nested instance — a plain
    ``vdc.rand()`` only supplies a scalar default of 0. Rewrite each such field's
    class attribute before the dataclass transform runs, preserving its metadata
    (so rand-ness from ``vdc.rand()``/``vdc.field()`` is retained)."""
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except Exception:
        return
    for name in list(getattr(cls, "__annotations__", {})):
        hint = hints.get(name)
        if not (isinstance(hint, type) and issubclass(hint, RandClass)):
            continue
        cur = cls.__dict__.get(name, dataclasses.MISSING)
        meta = dict(cur.metadata) if isinstance(cur, dataclasses.Field) else {}
        # If the user already supplied a default_factory, leave it alone.
        if (isinstance(cur, dataclasses.Field)
                and cur.default_factory is not dataclasses.MISSING):
            continue
        setattr(cls, name,
                dataclasses.field(default_factory=hint, metadata=meta))


@dataclass_transform(kw_only_default=True,
                     field_specifiers=(_rand, _randc, _field, dataclasses.field))
def dataclass(cls):
    """Transform ``cls`` into a vdc dataclass and attach its per-type model."""
    if issubclass(cls, RandClass):
        _fixup_composite_defaults(cls)
    cls = dataclasses.dataclass(kw_only=True)(cls)

    if issubclass(cls, RandClass):
        cls._vsc_type_model = build_type_model(cls)
    # Covergroup dispatch is added in Phase 3.

    return cls
