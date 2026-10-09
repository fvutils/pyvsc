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
from vsc.types import expr, to_expr

from . import cyclic, ir_lower, solve_view
from .constraint_ir import IRConst, IRModelLiteral

# Reuse an unchanged inline block across calls from one call site, so the
# randomizer's plan cache applies to randomize_with (V7). VSC_DC_INLINE_REUSE=0
# turns it off.
_INLINE_REUSE = os.environ.get("VSC_DC_INLINE_REUSE", "1") != "0"


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
    replaces the old one and the plan is rebuilt for it."""
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
        enter_expr_mode()
        push_constraint_scope(ConstraintBlockModel("inline"))
        return _InlineProxy(self._obj, self._field_models)

    def __exit__(self, t, v, tb):
        block = pop_constraint_scope()
        leave_expr_mode()
        if t is not None:
            # Propagate the user's exception; scopes already cleaned up.
            return False
        frame = sys._getframe(1)
        if _INLINE_REUSE:
            block = _reuse_block(self._composite, frame, block)
        # Writeback + post_randomize run inside do_randomize via the model rand_if.
        # The inline block is applied alongside the randc cyclic exclusions.
        cyclic.do_randomize_cyclic(
            self._obj, self._tm, self._obj._get_randstate(),
            SourceInfo(frame.f_code.co_filename, frame.f_lineno),
            self._composite, self._field_models, extra_blocks=[block],
            debug=self._debug, lint=self._lint,
            solve_fail_debug=self._solve_fail_debug)
        return False
