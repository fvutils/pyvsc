"""
Inline constraints (``randomize_with``) for the dataclass front-end.

Inline constraints are inherently per-call, so — unlike ``@vdc.constraint`` methods
— they are not AST-compiled or cached on the type. Instead this reuses pyvsc's
existing operator-overloading machinery: the ``it`` proxy yields ``expr`` objects
bound to *this* solve view's ``FieldScalarModel``s, the user's statements build the
``Expr*Model`` tree on the global expr stack, and ``__exit__`` harvests it into one
inline ``ConstraintBlockModel`` appended for that single solve.

See ``doc/notes/dataclass-pyvsc-design.md`` §4.6.
"""
import copy
import os
import sys

from vsc.impl.ctor import pop_constraint_scope, pop_expr, push_constraint_scope
from vsc.impl.expr_mode import enter_expr_mode, is_expr_mode, leave_expr_mode
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_cond_model import ExprCondModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_unary_model import ExprUnaryModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.randomizer import Randomizer, _plan_set
from vsc.model.solve_failure import SolveFailure
from vsc.model.source_info import SourceInfo
from vsc.model.expr_array_product_model import ExprArrayProductModel
from vsc.model.expr_array_sum_model import ExprArraySumModel
from vsc.model.field_array_model import FieldArrayModel
import vsc.types as vsc_types
from vsc.types import expr, expr_subscript, to_expr

from . import class_const, cyclic, inline_parse, ir_lower, solve_view
from .constraint_ir import IRConst, IRModelLiteral

# Reuse an unchanged inline block across calls from one call site, so the
# randomizer's plan cache applies to randomize_with (V7). VSC_DC_INLINE_REUSE=0
# turns it off.
_INLINE_REUSE = os.environ.get("VSC_DC_INLINE_REUSE", "1") != "0"

# Parse a randomize_with body with the @vdc.constraint grammar instead of
# executing it (inline_parse). On by default; VSC_DC_INLINE_PARSE=0 selects
# the operator-overloading path, which is also used when no source is found.
_INLINE_PARSE = os.environ.get("VSC_DC_INLINE_PARSE", "1") != "0"


class _FieldExpr(expr):
    """A field-ref expression whose ``[k]`` / ``[hi:lo]`` is a scalar part-select
    (matching ``type_base.__getitem__``), not array subscripting."""

    def __getitem__(self, rng):
        base_e = pop_expr()   # the field ref pushed by expr.__init__
        if isinstance(rng, slice):
            to_expr(rng.start)
            upper = pop_expr()
            to_expr(rng.stop)
            lower = pop_expr()
            return expr(ExprPartselectModel(base_e, upper, lower))
        to_expr(rng)
        idx = pop_expr()
        return expr(ExprPartselectModel(base_e, idx))


class _ArrayRef:
    """``it.<array>`` inside a legacy ``randomize_with`` body: ``[k]`` is an
    element (constant or symbolic index), and ``.size``, ``.sum`` and
    ``.product`` are the array's. It is not an ``expr`` itself, so it pushes
    nothing onto the expression stack until one of those is used."""

    __slots__ = ("_m",)

    def __init__(self, model):
        self._m = model

    def __getitem__(self, k):
        if isinstance(k, slice):
            raise TypeError("array slices are not supported in constraints")
        to_expr(k)
        return expr_subscript(ExprArraySubscriptModel(
            ExprFieldRefModel(self._m), pop_expr()))

    def to_expr(self):
        # The whole array, as vdc.foreach(it.arr) and the like take it.
        return _FieldExpr(ExprFieldRefModel(self._m))

    def __iter__(self):
        # Without this, Python iterates through __getitem__ and never stops.
        raise TypeError(
            "a loop over an array in randomize_with needs the body parsed "
            "(source available, VSC_DC_INLINE_PARSE on); use vdc.foreach")

    @property
    def size(self):
        return expr(ExprFieldRefModel(self._m.size))

    @property
    def sum(self):
        return expr(ExprArraySumModel(self._m))

    @property
    def product(self):
        return expr(ExprArrayProductModel(self._m))


class _InlineProxy:
    """The ``it`` handle. Dual-mode, mirroring the classic front-end where ``it``
    is the object itself: inside the ``with`` block (expr mode) ``it.<field>``
    yields a field-ref expression for constraint building; outside it (after the
    solve) it reads the solved value from the instance."""

    def __init__(self, obj, field_models):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_fm", field_models)

    def __getattr__(self, name):
        fm = object.__getattribute__(self, "_fm")
        model = fm.get(name)
        if model is None:
            # Not a field — it may be a generic constraint referenced inline
            # (``it.<name>()``, the analog of classic ``dynamic_constraint``).
            obj = object.__getattribute__(self, "_obj")
            tm = obj._get_type_model()
            prog = tm.generic_constraints.get(name)
            if prog is not None:
                if is_expr_mode():
                    return _GenericInlineRef(name, fm, tm.generic_constraints)
                raise AttributeError(
                    "generic constraint %r is only usable inside randomize_with"
                    % name)
            raise AttributeError(
                "no rand field %r to constrain in randomize_with" % name)
        if is_expr_mode():
            if isinstance(model, FieldArrayModel):
                return _ArrayRef(model)
            return _FieldExpr(ExprFieldRefModel(model))
        # Outside the with-block: behave like the object (return the value).
        return getattr(object.__getattribute__(self, "_obj"), name)


class _GenericInlineRef:
    """A generic-constraint reference inside a ``randomize_with`` block. Calling it
    (``it.foo(...)``) reifies the generic's body as a boolean term — usable as a
    bare statement or combined with ``|``/``&``/``~`` — mirroring classic
    ``dynamic_constraint``. Actual arguments may be int/bool/enum constants or
    field-valued expressions built from the ``it`` proxy (``it.x``, ``it.x + 1``)."""

    def __init__(self, name, field_models, generics):
        self._name = name
        self._fm = field_models
        self._generics = generics

    def __call__(self, *args, **kwargs):
        # Each ``expr`` actual pushed its model onto the global expr stack when it
        # was constructed (e.g. ``it.x``). Capture the models, then pop exactly that
        # many entries so the inline scope is not left with stray constraints.
        npops = [0]
        a = [self._actual_ir(v, npops) for v in args]
        kw = {k: self._actual_ir(v, npops) for k, v in kwargs.items()}
        for _ in range(npops[0]):
            pop_expr()
        return expr(ir_lower.lower_generic_ref(
            self._name, self._fm, self._generics, a, kw))

    def _actual_ir(self, v, npops):
        import enum
        if isinstance(v, expr):
            # A field-valued / compound actual built from the proxy: reuse its model.
            npops[0] += 1
            return IRModelLiteral(v.em)
        if isinstance(v, bool):
            return IRConst(int(v))
        if isinstance(v, enum.Enum):
            from vsc.impl.enum_info import EnumInfo
            return IRConst(EnumInfo.get(type(v)).e2v(v))
        if isinstance(v, int):
            return IRConst(v)
        raise TypeError(
            "inline argument to generic constraint %r must be an int/bool/enum "
            "constant or a field expression (got %r)"
            % (self._name, type(v).__name__))


def _truth_test(e):
    """``vsc.types.truth_hook`` while a body runs on the operator path."""
    raise TypeError(
        "a constraint expression was tested for truth ('and', 'or', 'not', "
        "'if', ...) in a randomize_with body that is not parsed: its source "
        "is not available, or VSC_DC_INLINE_PARSE=0. Use '&', '|', '~' and "
        "vdc.if_then there, or make the source available")


class _NoSig(Exception):
    """The block holds a node `_sig` does not know, so it is never reused."""


def _sig(n):
    """A hashable description of an inline-constraint tree: node types,
    operators, literal values and the identity of each referenced field model.
    Two blocks with equal signatures constrain the solve identically.

    Node types not listed here raise `_NoSig`. Such a block is not reused and
    takes the per-call path, so the list only needs to cover what is common;
    a missing type costs speed, not correctness."""
    if n is None:
        return None
    t = type(n)
    if t is ExprFieldRefModel:
        return (t, id(n.fm))
    if t is ExprLiteralModel:
        return (t, int(n._val.v), n.signed, n._width)
    if t is ExprBinModel:
        return (t, n.op, _sig(n.lhs), _sig(n.rhs))
    if t is ExprInModel:
        return (t, _sig(n.lhs), _sig(n.rhs))
    if t is ExprRangelistModel:
        return (t,) + tuple(_sig(r) for r in n.rl)
    if t is ExprRangeModel or t is ExprArraySubscriptModel:
        return (t, _sig(n.lhs), _sig(n.rhs))
    if t is ExprUnaryModel:
        return (t, n.op, _sig(n.expr))
    if t is ExprPartselectModel:
        return (t, _sig(n.lhs), _sig(n.upper), _sig(n.lower))
    if t is ExprCondModel:
        return (t, _sig(n.cond_e), _sig(n.true_e), _sig(n.false_e))
    if t is ConstraintExprModel:
        return (t, _sig(n.e))
    if t is ConstraintSoftModel:
        return (t, _sig(n.expr))
    if t is ConstraintImpliesModel:
        return (t, _sig(n.cond)) + tuple(_sig(c) for c in n.constraint_l)
    if t is ConstraintIfElseModel:
        return (t, _sig(n.cond), _sig(n.true_c), _sig(n.false_c))
    if t is ConstraintScopeModel or t is ConstraintBlockModel:
        return (t,) + tuple(_sig(c) for c in n.constraint_l)
    raise _NoSig(t.__name__)


def _shape(sig):
    """``sig`` with every literal value blanked: equal shapes mean two blocks
    differ at most in their literal values."""
    if type(sig) is not tuple:
        return sig
    if sig and sig[0] is ExprLiteralModel:
        return (ExprLiteralModel,)
    return tuple(_shape(s) for s in sig)


#: Attribute on a shared solve composite: {(code, line): (signature, block)}.
_SITES_ATTR = "_vsc_inline_sites"


def _reuse_block(composite, frame, block):
    """Return the block to solve with: the one this call site passed last time
    if ``block`` has the same content, otherwise ``block`` itself.

    Passing the same block object lets the randomizer reuse its plan (V7).
    Before this, an inline constraint disabled the plan cache, so every
    ``randomize_with`` rebuilt and re-translated the whole problem: 602 us
    against 30 us for the same rules written as a class constraint.

    A call site holds one block. When the content changes, the new block
    replaces the old one. If only literal values changed, the old block's plan
    may be moved to the new block (`_plan_rebind`); otherwise the plan is
    rebuilt for it."""
    try:
        sig = _sig(block)
    except _NoSig:
        return block
    sites = getattr(composite, _SITES_ATTR, None)
    if sites is None:
        sites = {}
        setattr(composite, _SITES_ATTR, sites)
    key = (frame.f_code, frame.f_lineno)
    prev = sites.get(key)
    if prev is not None:
        if prev[0] == sig:
            return prev[1]
        if _shape(prev[0]) == _shape(sig):
            # Only literal values changed: the randomizer may move the old
            # block's plan to this one (`_plan_rebind`), or drops it.
            block._vsc_rebind_from = prev[1]
            # A mark is consumed only when the plan cache runs (dv-solve);
            # clear the old block's so blocks don't chain.
            prev[1]._vsc_rebind_from = None
        else:
            # The site's old block is no longer passed, so its plan is dead.
            _plan_set(composite, (prev[1],), None)
    block._vsc_reusable = True
    sites[key] = (sig, block)
    return block


class RandomizeWith:
    """Context manager returned by ``RandClass.randomize_with()``."""

    def __init__(self, obj, debug=0, lint=0, solve_fail_debug=0):
        self._obj = obj
        self._debug = debug
        self._lint = lint
        self._solve_fail_debug = solve_fail_debug

    def __enter__(self):
        self._tm = self._obj._get_type_model()
        # Reuse the cached base composite (type constraints + fields); the inline
        # block is passed separately per call and not cached on the type.
        self._composite, self._field_models = solve_view.get_solve_model(
            self._obj, self._tm)
        self._parsed = None
        if _INLINE_PARSE:
            frame = sys._getframe(1)
            site = _parsed_site(frame, self._obj, self._tm)
            if site is not None:
                values = site.values(frame)
                if not site.fits(values):
                    # A structural host changed: the body for its new value.
                    site = _parsed_site(frame, self._obj, self._tm,
                                        site.struct_key(values))
                    values = site.values(frame)
                token = inline_parse.NO_SKIP if site.inert else \
                    inline_parse.skip_body(frame, site.body_line)
                if token is not None:
                    self._parsed = (site, values, token)
                    return _InlineProxy(self._obj, self._field_models)
        enter_expr_mode()
        push_constraint_scope(ConstraintBlockModel("inline"))
        self._saved_hook = vsc_types.truth_hook
        vsc_types.truth_hook = _truth_test
        return _InlineProxy(self._obj, self._field_models)

    def __exit__(self, t, v, tb):
        if self._parsed is not None:
            site, values, token = self._parsed
            inline_parse.release(token)
            if t is not None and t is not inline_parse.SkipBody:
                return False
            frame = sys._getframe(1)
            block = _parsed_block(self._composite, self._field_models,
                                  self._tm, site, values, frame)
            self._solve(frame, block)
            return True             # suppress SkipBody
        vsc_types.truth_hook = self._saved_hook
        block = pop_constraint_scope()
        leave_expr_mode()
        if t is not None:
            # Propagate the user's exception; scopes already cleaned up.
            return False
        frame = sys._getframe(1)
        if _INLINE_REUSE:
            block = _reuse_block(self._composite, frame, block)
        self._solve(frame, block)
        return False

    def _solve(self, frame, block):
        # Writeback + post_randomize run inside do_randomize via the model rand_if.
        # The inline block is applied alongside the randc cyclic exclusions.
        cyclic.do_randomize_cyclic(
            self._obj, self._tm, self._obj._get_randstate(),
            SourceInfo(frame.f_code.co_filename, frame.f_lineno),
            self._composite, self._field_models, extra_blocks=[block],
            debug=self._debug, lint=self._lint,
            solve_fail_debug=self._solve_fail_debug)


def _parsed_site(frame, obj, tm, struct_key=None):
    """The parsed body of the randomize_with ``frame`` is entering, for
    ``obj``'s class (class constants folded, references checked), or None to
    take the legacy path (no source, no 'as' name, a one-line body).

    ``struct_key`` selects the body parsed for those structural host values
    (see ``inline_parse.Site.fits``); it is parsed now if it is new."""
    loc = inline_parse.locate(frame)
    if loc is None or loc.body_line is None:
        return None
    cls = type(obj) if struct_key is None else (type(obj), struct_key)
    site = loc.sites.get(cls)
    if site is _LEGACY:
        return None
    if site is None:
        if loc.deleg is None:
            loc.deleg = inline_parse.delegates(loc.node.body, loc.it_name)
        if loc.deleg:
            loc.sites[cls] = _LEGACY
            return None
        from . import class_const
        from .type_model import _validate_refs
        fields = frozenset(f.name for f in tm.fields)
        arrays = frozenset(f.name for f in tm.fields if f.is_array)
        key = (arrays, fields, struct_key)
        base = loc.parsed.get(key)
        if base is None:
            base = inline_parse.compile_site(loc, frame, arrays, fields)
            base.body_line = loc.body_line
            base.inert = inline_parse.inert(loc.node.body)
            loc.parsed[key] = base
        # Only the class constants differ between classes with these fields.
        site = copy.copy(base)
        site.folded = class_const.fold_program(
            site.prog, class_const.lookup_for(type(obj), fields))
        _validate_refs(tm.cls_name, [site.folded], tm.generic_constraints,
                       fields)
        loc.sites[cls] = site
    return site


#: Marks a call site whose body must run (see inline_parse.delegates).
_LEGACY = object()

#: Most folded programs a site keeps, one per value of its condition slots.
_FOLD_CACHE_MAX = 64

#: Attribute on a shared solve composite: {site: (host values, block)}.
_PARSED_ATTR = "_vsc_inline_parsed"


def _parsed_block(composite, field_models, tm, site, values, frame):
    """The block for a parsed body: the one this site used last time when the
    host values are the same (so the plan is reused), else a new lowering."""
    cache = getattr(composite, _PARSED_ATTR, None)
    if cache is None:
        cache = {}
        setattr(composite, _PARSED_ATTR, cache)
    prev = cache.get(site)
    if prev is not None and prev[0] == values:
        return prev[1]
    # A host condition decides its branch here, as running the body would.
    # Only the condition slots are folded, once per their values; lowering
    # writes the other host values in as literals.
    control = site.control
    if control is None:
        control = site.control = class_const.host_control_slots(site.folded)
        site.fold_cache = {}
    key = tuple([values[k] for k in control])
    prog = site.fold_cache.get(key)
    if prog is None:
        if len(site.fold_cache) >= _FOLD_CACHE_MAX:
            site.fold_cache.clear()
        prog = site.fold_cache[key] = class_const.fold_host_values(
            site.folded, values, frozenset(control))
    block = ir_lower.lower_program(prog, field_models, tm.generic_constraints,
                                   values)
    if _INLINE_REUSE:
        block = _reuse_block(composite, frame, block)
    cache[site] = (values, block)
    return block
