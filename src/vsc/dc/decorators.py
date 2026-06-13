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


@dataclass_transform(kw_only_default=True,
                     field_specifiers=(_rand, _randc, _field, dataclasses.field))
def dataclass(cls):
    """Transform ``cls`` into a vdc dataclass and attach its per-type model."""
    cls = dataclasses.dataclass(kw_only=True)(cls)

    if issubclass(cls, RandClass):
        cls._vsc_type_model = build_type_model(cls)
    # Covergroup dispatch is added in Phase 3.

    return cls
