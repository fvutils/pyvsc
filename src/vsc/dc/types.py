"""
Type aliases for the dataclass (``vsc.dc``) front-end.

Field types are plain ``Annotated[int, _Width(bits, signed)]`` aliases. Width and
signedness are recovered *statically* at type-elaboration time via
``typing.get_type_hints(cls, include_extras=True)`` + :func:`width_of`, so there is
no stateful field object and no per-instance work.

See ``doc/notes/dataclass_pyvsc_impl_test_doc_plan.md`` §2.2.
"""
from typing import Annotated, Optional, Tuple


class _Width:
    """Annotation marker carrying a field's bit-width and signedness.

    Attached to an ``int`` via ``typing.Annotated`` so it is visible to static
    type checkers as ``int`` while remaining introspectable at runtime.
    """

    __slots__ = ("bits", "signed")

    def __init__(self, bits: int, signed: bool):
        self.bits = bits
        self.signed = signed

    def __repr__(self):
        return "_Width(%d, %s)" % (self.bits, "signed" if self.signed else "unsigned")

    def __eq__(self, other):
        return (isinstance(other, _Width)
                and other.bits == self.bits
                and other.signed == self.signed)

    def __hash__(self):
        return hash((self.bits, self.signed))


def width_of(annotation) -> Optional[Tuple[int, bool]]:
    """Recover ``(bits, signed)`` from a ``vdc`` type annotation.

    Returns ``None`` for annotations that carry no :class:`_Width` marker (e.g. a
    bare ``int`` or a runtime-width ``bitv`` that relies on an explicit
    ``rand(width=...)``).
    """
    meta = getattr(annotation, "__metadata__", None)
    if meta:
        for m in meta:
            if isinstance(m, _Width):
                return (m.bits, m.signed)
    return None


# ---------------------------------------------------------------------------
# Alias table. u1..u64 (unsigned) and s1..s64 (signed) are generated; the common
# byte-width signed aliases are also exposed as s8/s16/s32/s64 (identical to the
# generated forms — kept for readability and to mirror the design doc).
# ---------------------------------------------------------------------------

# Runtime-width integer: width supplied via vdc.rand(width=...)/vdc.field(width=...).
bitv = Annotated[int, _Width(-1, False)]

_g = globals()
for _b in range(1, 65):
    _g["u%d" % _b] = Annotated[int, _Width(_b, False)]
    _g["s%d" % _b] = Annotated[int, _Width(_b, True)]
del _g, _b

# ---------------------------------------------------------------------------
# Inclusive range-slice helper
# ---------------------------------------------------------------------------

class _RangeSlice:
    """``vdc.r[lo:hi]`` — an **inclusive** value range, the closest legal Python
    spelling of SystemVerilog's ``inside {[lo:hi]}``.

    Inside a ``@vdc.constraint`` body this is recognized by the AST parser and is
    never executed; the runtime behaviour here exists so the object is real outside
    a constraint (and so a typo surfaces as a normal error rather than silence).

        self.a in vdc.r[3:50]              # 3..50 inclusive
        self.a in vdc.r[3:50, 100:200]     # a union of inclusive ranges

    Contrast ``range(3, 50)``, which is **half-open** (3..49) because that is what
    ``range`` means in Python. Both spellings are accepted; they differ at the upper
    endpoint, deliberately.
    """

    __slots__ = ()

    def __getitem__(self, key):
        # Imported lazily: this is a cold path, and vsc.types pulls in the whole
        # expression machinery, which dc.types must not depend on at import time.
        from vsc.types import rangelist, rng
        items = key if isinstance(key, tuple) else (key,)
        out = []
        for it in items:
            if not isinstance(it, slice):
                raise TypeError(
                    "vdc.r takes range slices (r[lo:hi]); got %r" % (it,))
            if it.step is not None:
                raise TypeError("vdc.r does not support a step (r[lo:hi:step])")
            if it.start is None or it.stop is None:
                raise TypeError("vdc.r requires explicit bounds (r[lo:hi])")
            out.append(rng(it.start, it.stop))
        return rangelist(*out)

    def __repr__(self):
        return "vdc.r"


r = _RangeSlice()


# Explicit, documented exports (the generated names above are all valid too).
__all__ = ["_Width", "width_of", "bitv", "r"] \
    + ["u%d" % b for b in range(1, 65)] \
    + ["s%d" % b for b in range(1, 65)]
