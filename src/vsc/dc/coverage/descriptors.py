"""
Coverage descriptors + annotation markers for the dataclass front-end.

``vdc.coverpoint(...)`` / ``vdc.cross(...)`` return descriptor objects that hold
the *type-level* definition (parsed once, frozen on the CovergroupTypeModel). Per
instance, ``__get__`` returns the lightweight runtime ``Coverpoint``/``Cross``
object from ``obj._cp_insts`` / ``obj._cr_insts``.

A coverpoint field is annotated ``vdc.Coverpoint[T]`` (a cross ``vdc.Cross``); the
generic parameter ``T`` carries the sampled value's width/signedness, recovered at
decoration time (see ``type_model.prepare_covergroup``). This mirrors the design in
``doc/notes/dataclass-pyvsc-design.md`` §5.4.
"""
import itertools
from typing import Generic, TypeVar

from vsc.impl.enum_info import EnumInfo

T = TypeVar("T")

# Monotonic declaration-order counter (coverpoints/crosses are not dataclass
# fields, so ordering is recovered from creation order, à la Django fields).
_order = itertools.count()


class Coverpoint(Generic[T]):
    """Per-instance runtime coverpoint object; also the ``Coverpoint[T]`` field
    annotation marker. Wraps the classic ``CoverpointModel`` and stages a pushed
    value via :meth:`set`."""

    def __init__(self, name, model, enum_cls=None):
        self._name = name
        self._model = model            # classic CoverpointModel (the runtime seam)
        self._enum_cls = enum_cls
        self._staged = 0               # push value, binned on the next sample()

    def set(self, value):
        """Stage a value for a *push* coverpoint (binned on the next sample())."""
        self._staged = _to_int(value, self._enum_cls)

    @property
    def value(self):
        return self._staged

    def get_inst_coverage(self):
        return self._model.get_inst_coverage()

    get_coverage = get_inst_coverage

    def get_bin_hits(self, idx):
        return self._model.get_bin_hits(idx)


class Cross:
    """Per-instance runtime cross object; also the ``Cross`` field annotation."""

    def __init__(self, name, model):
        self._name = name
        self._model = model

    def get_coverage(self):
        return self._model.get_coverage()

    get_inst_coverage = get_coverage


def _to_int(value, enum_cls):
    if enum_cls is not None and not isinstance(value, int):
        return EnumInfo.get(enum_cls).e2v(value)
    return int(value)


class _CPDescriptor:
    """Type-level coverpoint definition (frozen on the CovergroupTypeModel)."""

    def __init__(self, ref, bins, iff, ignore_bins, illegal_bins, cp_t, options):
        self.ref = ref                 # callable(self)->value, or None for push
        self.bins = bins               # dict {name: bin/bin_array spec}, or None=auto
        self.iff = iff                 # callable(self)->bool guard, or None
        self.ignore_bins = ignore_bins
        self.illegal_bins = illegal_bins
        self.cp_t = cp_t               # explicit type override (enum class / width type)
        self.options = options         # dict of CoverageOptions overrides, or None
        self.order = next(_order)
        self.name = None
        # Resolved at decoration time from the Coverpoint[T] annotation / cp_t:
        self.width = None
        self.signed = False
        self.enum_cls = None

    @property
    def is_push(self):
        return self.ref is None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj._cp_insts[self.name]


class _CrossDescriptor:
    """Type-level cross definition: a list of target coverpoints (by lambda)."""

    def __init__(self, targets, ignore_bins, illegal_bins, options):
        self.targets = list(targets)   # callables(self)->Coverpoint runtime obj
        self.ignore_bins = ignore_bins
        self.illegal_bins = illegal_bins
        self.options = options
        self.order = next(_order)
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj._cr_insts[self.name]


class _BinsofExpr:
    """Base for the ``binsof`` cross-bin selection DSL (SV-1800 §19.6). Terms and
    their ``& | ~`` combinations form a tiny expression tree compiled to a
    ``func(*bin_l)`` predicate at cross-build time (see covergroup._compile_binsof).
    """

    def __and__(self, other):
        return _BinsofAnd(self, other)

    def __or__(self, other):
        return _BinsofOr(self, other)

    def __invert__(self):
        return _BinsofNot(self)


class _BinsofTerm(_BinsofExpr):
    """``binsof(cp)`` (whole coverpoint, ``values is None``) or
    ``binsof(cp).intersect(values)`` (component bins overlapping ``values``)."""

    def __init__(self, cp, values=None):
        self.cp = cp                   # runtime Coverpoint object (identity -> position)
        self.values = values           # list of points / (lo,hi) tuples, or None

    def intersect(self, values):
        return _BinsofTerm(self.cp, list(values))


class _BinsofAnd(_BinsofExpr):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs


class _BinsofOr(_BinsofExpr):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs


class _BinsofNot(_BinsofExpr):
    def __init__(self, operand):
        self.operand = operand


def binsof(cp):
    """Select the cross bins whose component-``cp`` bin is in ``cp`` (SV §19.6).
    ``cp`` is a coverpoint of the cross, referenced like the cross targets
    (``vdc.binsof(s.a)``). Narrow with ``.intersect([points/(lo,hi)...])``; combine
    selections with ``&`` / ``|`` / ``~``. Used as a cross ``ignore_bins`` /
    ``illegal_bins`` value, ``{name: lambda s: <binsof expr>}``."""
    if not isinstance(cp, Coverpoint):
        raise TypeError(
            "binsof() expects a cross coverpoint (e.g. binsof(s.a)); got %r"
            % type(cp).__name__)
    return _BinsofTerm(cp)


def coverpoint(ref=None, *, bins=None, iff=None, ignore_bins=None,
               illegal_bins=None, cp_t=None, options=None):
    """Declare a coverpoint. ``ref=lambda s: <expr>`` makes it *pull* (value read
    from state at sample time); no ``ref`` makes it *push* (stage via ``.set()`` or
    the synthesized ``sample()`` formal). ``bins`` is a dict of ``vdc.bin``/
    ``vdc.bin_array`` specs; omit for automatic bins from the ``Coverpoint[T]``
    width/enum."""
    return _CPDescriptor(ref, bins, iff, ignore_bins, illegal_bins, cp_t, options)


def cross(*targets, ignore_bins=None, illegal_bins=None, options=None):
    """Declare a cross of two or more coverpoints, referenced by lambda
    (``vdc.cross(lambda s: s.op, lambda s: s.mode)``)."""
    return _CrossDescriptor(targets, ignore_bins, illegal_bins, options)
