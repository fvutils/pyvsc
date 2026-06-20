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
import sys

from vsc.impl.ctor import pop_constraint_scope, pop_expr, push_constraint_scope
from vsc.impl.expr_mode import enter_expr_mode, is_expr_mode, leave_expr_mode
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.randomizer import Randomizer
from vsc.model.solve_failure import SolveFailure
from vsc.model.source_info import SourceInfo
from vsc.types import expr, to_expr

from . import ir_lower, solve_view
from .constraint_ir import IRConst


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
    ``dynamic_constraint``. Actual arguments must be int/bool/enum constants (a
    field-valued actual is a follow-on; reference such generics from a
    ``@vdc.constraint`` instead)."""

    def __init__(self, name, field_models, generics):
        self._name = name
        self._fm = field_models
        self._generics = generics

    def __call__(self, *args, **kwargs):
        a = [self._actual_ir(v) for v in args]
        kw = {k: self._actual_ir(v) for k, v in kwargs.items()}
        return expr(ir_lower.lower_generic_ref(
            self._name, self._fm, self._generics, a, kw))

    def _actual_ir(self, v):
        import enum
        if isinstance(v, bool):
            return IRConst(int(v))
        if isinstance(v, enum.Enum):
            from vsc.impl.enum_info import EnumInfo
            return IRConst(EnumInfo.get(type(v)).e2v(v))
        if isinstance(v, int):
            return IRConst(v)
        raise TypeError(
            "inline argument to generic constraint %r must be an int/bool/enum "
            "constant (got %r); reference it from a @vdc.constraint for "
            "field-valued actuals" % (self._name, type(v).__name__))


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
        # Writeback + post_randomize run inside do_randomize via the model rand_if.
        Randomizer.do_randomize(
            self._obj._get_randstate(),
            SourceInfo(frame.f_code.co_filename, frame.f_lineno),
            [self._composite], [block],
            debug=self._debug, lint=self._lint,
            solve_fail_debug=self._solve_fail_debug)
        return False
