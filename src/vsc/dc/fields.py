"""
Field-declaration factories for the dataclass (``vsc.dc``) front-end.

These produce ``dataclasses.field(...)`` objects whose ``metadata`` carries a
:class:`FieldMeta` describing rand-ness, domain, array sizing, etc. No stateful
field objects, no operator overloading — exactly the zuspec pattern
(see ``doc/notes/dataclass-pyvsc-design.md`` §2.1).

The metadata is read once per type by ``type_model.build_type_model`` to produce
``FieldDecl``s; instances carry only plain values.
"""
import dataclasses
from typing import Any, Optional, Tuple

# Key under which FieldMeta is stored in dataclasses.Field.metadata.
META_KEY = "vsc_dc"

# Sentinel for "no default supplied" (distinct from a default of None/0).
_MISSING = dataclasses.MISSING


@dataclasses.dataclass(frozen=True)
class FieldMeta:
    """Type-level description of a dataclass field, recorded in field metadata.

    ``role`` distinguishes random fields from coverage formals/bindings:
      - ``"rand"`` / ``"randc"`` — solver fields
      - ``""``                    — plain (non-rand) state
      - ``"cg_arg"``              — read-through binding to an external object (coverage)
      - ``"sample_arg"``          — persistent sample formal (coverage)
    """
    role: str = ""
    domain: Optional[Tuple[int, int]] = None
    size: Optional[int] = None
    max_size: Optional[int] = None
    soft: Any = None
    width: Optional[int] = None       # explicit width override (paired with vdc.bitv)
    signed: Optional[bool] = None     # explicit sign override

    @property
    def is_rand(self) -> bool:
        return self.role in ("rand", "randc")


def _mk(default, default_factory, meta: FieldMeta):
    """Build a dataclasses.field with our metadata, honoring default/default_factory."""
    md = {META_KEY: meta}
    if default_factory is not _MISSING:
        return dataclasses.field(default_factory=default_factory, metadata=md)
    if default is not _MISSING:
        return dataclasses.field(default=default, metadata=md)
    # A fixed-size array defaults to a zero-filled list of that size (mutable, so it
    # must use default_factory). Random-size arrays default to an empty list.
    if meta.size is not None:
        n = meta.size
        return dataclasses.field(default_factory=lambda: [0] * n, metadata=md)
    if meta.size is None and (meta.max_size is not None):
        return dataclasses.field(default_factory=list, metadata=md)
    # Scalar rand/field with no explicit default: default to 0 so `T()` constructs
    # with no required kwargs (matches legacy pyvsc, where fields start at 0).
    return dataclasses.field(default=0, metadata=md)


def rand(*, domain=None, size=None, max_size=None, soft=None,
         width=None, signed=None, default=_MISSING, default_factory=_MISSING):
    """A random field. ``domain=(lo,hi)`` restricts the value range; ``size``/
    ``max_size`` declare (random-size) arrays; ``width``/``signed`` override the
    annotation (needed for ``vdc.bitv``)."""
    return _mk(default, default_factory,
               FieldMeta(role="rand", domain=domain, size=size,
                         max_size=max_size, soft=soft, width=width, signed=signed))


def randc(*, domain=None, size=None, max_size=None,
          width=None, signed=None, default=_MISSING, default_factory=_MISSING):
    """A cyclic-random field (visits its full domain before repeating)."""
    return _mk(default, default_factory,
               FieldMeta(role="randc", domain=domain, size=size,
                         max_size=max_size, width=width, signed=signed))


def field(*, default=_MISSING, default_factory=_MISSING, width=None, signed=None):
    """A plain (non-rand) field: covergroup/random state that constraints and
    coverpoints may reference but the solver does not assign."""
    return _mk(default, default_factory,
               FieldMeta(role="", width=width, signed=signed))


# --- Coverage formals (structure reserved in Phase 0; consumed in Phase 3) ---

def cg_arg(*, default=None):
    """A read-through binding to an external object the covergroup samples."""
    return _mk(default, _MISSING, FieldMeta(role="cg_arg"))


def sample_arg(*, default=_MISSING, default_factory=_MISSING, width=None, signed=None):
    """A persistent sample formal: receives a value at sample() time and feeds
    one or more pull coverpoints."""
    return _mk(default, default_factory,
               FieldMeta(role="sample_arg", width=width, signed=signed))


def get_field_meta(f: dataclasses.Field) -> Optional[FieldMeta]:
    """Return the :class:`FieldMeta` attached to a dataclasses.Field, or None."""
    return f.metadata.get(META_KEY)
