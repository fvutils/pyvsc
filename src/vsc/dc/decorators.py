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

from .coverage.covergroup import Covergroup
from .coverage.type_model import build_cg_type_model, prepare_covergroup
from .fields import field as _field, rand as _rand, randc as _randc
from .rand_class import RandClass
from .type_model import CONSTRAINT_ATTR, build_type_model


def constraint(func):
    """Tag a method as a constraint. The body is parsed (not executed) once per
    type by the constraint compiler."""
    setattr(func, CONSTRAINT_ATTR, True)
    return func


def _fixup_composite_defaults(cls):
    """Composite fields need a ``default_factory`` that constructs fresh nested
    instances — a plain ``vdc.rand()`` only supplies a scalar default of 0.
    Rewrite each such field's class attribute before the dataclass transform runs,
    preserving its metadata (so rand-ness from ``vdc.rand()``/``vdc.field()`` and
    the array ``size=`` are retained):
      - ``sub: Sub``            -> default_factory = Sub
      - ``arr: list[Sub]``  (size=N) -> default_factory = [Sub() for _ in range(N)]
    """
    from .fields import get_field_meta
    from .type_model import _list_element
    try:
        hints = typing.get_type_hints(cls, include_extras=True)
    except Exception:
        return
    for name in list(getattr(cls, "__annotations__", {})):
        hint = hints.get(name)
        cur = cls.__dict__.get(name, dataclasses.MISSING)
        meta = dict(cur.metadata) if isinstance(cur, dataclasses.Field) else {}
        has_factory = (isinstance(cur, dataclasses.Field)
                       and cur.default_factory is not dataclasses.MISSING)
        if isinstance(hint, type) and issubclass(hint, RandClass):
            # Scalar nested composite. A scalar default of 0 needs replacing; an
            # explicit default_factory is respected.
            if not has_factory:
                setattr(cls, name,
                        dataclasses.field(default_factory=hint, metadata=meta))
            continue
        elem = _list_element(hint)
        if isinstance(elem, type) and issubclass(elem, RandClass):
            # Composite array. The size-driven auto factory builds ``[0]*n`` (wrong
            # for objects), so replace it with one constructing N element instances.
            # Fixed-size pre-allocates ``size`` elements; random-size pre-allocates
            # ``max_size`` (the upper bound the solver picks ``size`` within).
            fm = get_field_meta(cur) if isinstance(cur, dataclasses.Field) else None
            n = None
            if fm is not None:
                n = fm.size if fm.size is not None else fm.max_size
            if n is not None:
                setattr(cls, name, dataclasses.field(
                    default_factory=(lambda e=elem, k=n: [e() for _ in range(k)]),
                    metadata=meta))


@dataclass_transform(kw_only_default=True,
                     field_specifiers=(_rand, _randc, _field, dataclasses.field))
def dataclass(cls):
    """Transform ``cls`` into a vdc dataclass and attach its per-type model(s)."""
    is_rand = issubclass(cls, RandClass)
    is_cg = issubclass(cls, Covergroup)
    if is_rand:
        _fixup_composite_defaults(cls)
    if is_cg:
        # Resolve coverpoint widths + strip coverpoint/cross attrs from the
        # annotations so they stay descriptors, not dataclass data fields.
        prepare_covergroup(cls)

    cls = dataclasses.dataclass(kw_only=True)(cls)

    if is_rand:
        cls._vsc_type_model = build_type_model(cls)
    if is_cg:
        cls._vsc_cg_type_model = build_cg_type_model(cls)

    return cls
