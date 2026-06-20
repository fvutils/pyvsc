"""
Lower instance-independent :mod:`vsc.dc.constraint_ir` into pyvsc's existing
``Expr*Model`` / ``Constraint*Model`` objects — **per randomize call**, binding
``IRField`` references to that instance's field models by name.

Resolution goes through a small :class:`Ctx` so that foreach loop variables (and,
later, nested composites) bind cleanly without threading extra parameters: the
base scope maps field names to their models; ``foreach`` pushes the loop's
index / element bindings.
"""
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_dist_model import ConstraintDistModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.constraint_solve_order_model import ConstraintSolveOrderModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.dist_weight_expr_model import DistWeightExprModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_array_sum_model import ExprArraySumModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_dynref_model import ExprDynRefModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_unary_model import ExprUnaryModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.unary_expr_type import UnaryExprType

from . import constraint_ir as ir

# IR op token -> BinExprType (matches vsc.types.expr operators).
_BIN = {
    "==": BinExprType.Eq, "!=": BinExprType.Ne, "<": BinExprType.Lt,
    "<=": BinExprType.Le, ">": BinExprType.Gt, ">=": BinExprType.Ge,
    "+": BinExprType.Add, "-": BinExprType.Sub, "*": BinExprType.Mul,
    "//": BinExprType.Div, "%": BinExprType.Mod, "&": BinExprType.And,
    "|": BinExprType.Or, "^": BinExprType.Xor, "<<": BinExprType.Sll,
    ">>": BinExprType.Srl,
}


class Ctx:
    """Name-resolution context for lowering one constraint program."""

    def __init__(self, field_models, generics=None):
        self.fields = field_models           # name -> FieldModel
        self.locals = {}                      # name -> callable() -> ExprModel
        self.model_locals = {}               # name -> FieldModel (composite elem)
        self.const_locals = {}               # name -> int (unrolled foreach index)
        self.generics = generics or {}        # name -> ConstraintProgram (generic/value)
        self._active = frozenset()            # generics being expanded (cycle guard)

    def model(self, name):
        return self.fields.get(name)

    def _child(self):
        c = Ctx(self.fields, self.generics)
        c.locals = dict(self.locals)
        c.model_locals = dict(self.model_locals)
        c.const_locals = dict(self.const_locals)
        c._active = self._active
        return c

    def activate(self, name):
        """Return a child Ctx marking ``name`` as being expanded (cycle guard)."""
        c = self._child()
        c._active = self._active | {name}
        return c

    def with_local(self, name, factory):
        """Return a child Ctx with one extra expr local binding (scalar foreach)."""
        c = self._child()
        if name is not None:
            c.locals[name] = factory
        return c

    def with_model_local(self, name, model):
        """Return a child Ctx binding ``name`` to a concrete element model
        (composite foreach element)."""
        c = self._child()
        if name is not None:
            c.model_locals[name] = model
        return c

    def with_const_local(self, name, value):
        """Return a child Ctx binding ``name`` to a constant int (unrolled foreach
        index), usable both as a value and as a constant array subscript."""
        c = self._child()
        if name is not None:
            c.const_locals[name] = value
        return c


def lower_program(prog, field_models, generics=None):
    """Build a fresh :class:`ConstraintBlockModel` from ``prog`` binding fields
    via ``field_models`` (name -> model). ``generics`` is the type's generic/value
    constraint registry, used to resolve ``IRConstraintRef`` references."""
    ctx = Ctx(field_models, generics)
    block = ConstraintBlockModel(prog.name)
    for stmt in prog.stmts:
        block.constraint_l.append(_stmt(stmt, ctx))
    return block


def _bind_params(ctx, prog, ref):
    """Return a child Ctx binding each of ``prog``'s formals to its actual argument
    (positional/keyword/default, resolved by ir.bind_actuals), lowered in the
    *caller's* scope (``ctx``). Each formal use re-lowers the actual (fresh model
    per occurrence, matching foreach-local semantics)."""
    actuals = ir.bind_actuals(prog.name, prog.params, prog.param_defaults,
                              ref.args, ref.kwargs)
    child = ctx
    for pname, arg in zip(prog.params, actuals):
        child = child.with_local(pname, (lambda a, c: (lambda: _expr(a, c)))(arg, ctx))
    return child


def _ref_stmt(node, ctx):
    """Lower a generic-constraint reference in statement position: splice the whole
    body into a fresh scope."""
    prog = ctx.generics.get(node.name)
    if prog is None:
        raise KeyError("reference to unknown generic constraint %r" % node.name)
    if prog.kind == "value":
        raise TypeError("value generic %r cannot be referenced as a statement"
                        % node.name)
    if node.name in ctx._active:
        raise ValueError("recursive generic-constraint reference %r" % node.name)
    child = _bind_params(ctx.activate(node.name), prog, node)
    scope = ConstraintScopeModel()
    for s in prog.stmts:
        scope.constraint_l.append(_stmt(s, child))
    return scope


# Statement kinds with a boolean value — the only ones meaningful when a generic
# is reified as a boolean term (matches type_model._BOOLEAN_OK_STMT).
_BOOLEAN_REF_OK = (ir.IRConstraintExpr, ir.IRIfElse, ir.IRImplies,
                   ir.IRUnique, ir.IRConstraintRef)


def lower_generic_ref(name, field_models, generics, args=None, kwargs=None):
    """Lower a generic-constraint reference to an ExprDynRefModel, for inline
    ``randomize_with`` references (``it.<name>(...)``). ``args``/``kwargs`` are IR
    actuals (constants for the inline path). Boolean-bodied generics only — the
    inline path always reifies the block as a boolean term."""
    prog = generics.get(name)
    if prog is None:
        raise KeyError("unknown generic constraint %r" % name)
    if prog.kind == "value":
        raise TypeError(
            "value generic %r cannot be referenced as a constraint" % name)
    if any(not isinstance(s, _BOOLEAN_REF_OK) for s in prog.stmts):
        raise TypeError(
            "generic %r contains a non-boolean item (soft/dist/solve_order/foreach) "
            "and cannot be referenced in randomize_with; reference it from a "
            "@vdc.constraint instead" % name)
    ctx = Ctx(field_models, generics)
    return _ref_expr(ir.IRConstraintRef(name, args or [], 0, kwargs or {}), ctx)


def _ref_expr(node, ctx):
    """Lower a generic-constraint reference in expression/boolean position. A value
    generic inlines its returned expression; a boolean generic is reified as a
    boolean term via ExprDynRefModel (reusing the dynamic-constraint backend path)."""
    prog = ctx.generics.get(node.name)
    if prog is None:
        raise KeyError("reference to unknown generic constraint %r" % node.name)
    if node.name in ctx._active:
        raise ValueError("recursive generic-constraint reference %r" % node.name)
    child = _bind_params(ctx.activate(node.name), prog, node)
    if prog.kind == "value":
        return _expr(prog.ret, child)
    block = ConstraintBlockModel(node.name)
    for s in prog.stmts:
        block.constraint_l.append(_stmt(s, child))
    return ExprDynRefModel(block)


def _stmt(node, ctx):
    if isinstance(node, ir.IRConstraintRef):
        return _ref_stmt(node, ctx)
    if isinstance(node, ir.IRConstraintExpr):
        return ConstraintExprModel(_expr(node.expr, ctx))
    if isinstance(node, ir.IRIfElse):
        return _if_else(node, ctx)
    if isinstance(node, ir.IRImplies):
        body = [_stmt(s, ctx) for s in node.body]
        return ConstraintImpliesModel(_expr(node.cond, ctx), body)
    if isinstance(node, ir.IRSoft):
        return ConstraintSoftModel(_expr(node.expr, ctx))
    if isinstance(node, ir.IRUnique):
        return ConstraintUniqueModel([_expr(t, ctx) for t in node.terms])
    if isinstance(node, ir.IRSolveOrder):
        before = [ctx.model(f.name) for f in node.before]
        after = [ctx.model(f.name) for f in node.after]
        return ConstraintSolveOrderModel(before, after)
    if isinstance(node, ir.IRForeach):
        return _foreach(node, ctx)
    if isinstance(node, ir.IRDist):
        return _dist(node, ctx)
    raise NotImplementedError("lower statement %r" % type(node).__name__)


def _dist(node, ctx):
    lhs = _expr(node.lhs, ctx)
    weights = []
    for w in node.weights:
        rng_lhs = ExprLiteralModel(w.lo, True, 32)
        rng_rhs = ExprLiteralModel(w.hi, True, 32) if w.hi is not None else None
        # Weight is a general expression: a literal (static) or a field ref read at
        # solve time (dynamic). The plan-cache dist_state snapshot detects changes.
        weights.append(DistWeightExprModel(
            rng_lhs, rng_rhs, _expr(w.weight, ctx),
            is_per_value=w.per_value))
    return ConstraintDistModel(lhs, weights)


def _foreach(node, ctx):
    arr = _resolve_model(node.array, ctx)
    if not isinstance(arr, FieldArrayModel):
        raise TypeError("foreach target %r is not an array" % (node.array,))
    if not arr.is_scalar:
        # Composite-element array: unroll over the concrete elements so element
        # fields bind directly (no ExprArraySubscript-of-composite machinery).
        return _foreach_composite(node, ctx, arr)
    # ConstraintForeachModel.lhs is an expression (ExprFieldRefModel), matching the
    # classic front-end — the array-constraint builder resolves the array from it.
    arr_ref = ExprFieldRefModel(arr)
    stmt = ConstraintForeachModel(arr_ref)
    index = stmt.index
    # Bind loop variables: idx -> the index field; it -> the element subscript.
    child = ctx
    if node.idx_name is not None:
        child = child.with_local(
            node.idx_name, lambda: ExprFieldRefModel(index))
    if node.it_name is not None:
        child = child.with_local(
            node.it_name,
            lambda: ExprArraySubscriptModel(arr_ref, ExprFieldRefModel(index)))
    for s in node.body:
        stmt.constraint_l.append(_stmt(s, child))
    return stmt


def _foreach_composite(node, ctx, arr):
    """Unroll a foreach over a (fixed-size) composite-element array: for each
    element, bind ``it`` to that element's model and ``idx`` to the literal index,
    then lower the body. Produces one ConstraintScopeModel of plain constraints."""
    scope = ConstraintScopeModel()
    for i, elem in enumerate(arr.field_l):
        child = ctx
        if node.idx_name is not None:
            child = child.with_const_local(node.idx_name, i)
        if node.it_name is not None:
            child = child.with_model_local(node.it_name, elem)
        for s in node.body:
            scope.constraint_l.append(_stmt(s, child))
    return scope


def _if_else(node, ctx):
    true_c = _scope(node.true_body, ctx)
    false_c = None
    if node.false_body is not None:
        if len(node.false_body) == 1 and isinstance(node.false_body[0], ir.IRIfElse):
            false_c = _if_else(node.false_body[0], ctx)
        else:
            false_c = _scope(node.false_body, ctx)
    return ConstraintIfElseModel(_expr(node.cond, ctx), true_c, false_c)


def _scope(stmts, ctx):
    scope = ConstraintScopeModel()
    for s in stmts:
        scope.constraint_l.append(_stmt(s, ctx))
    return scope


def _expr(node, ctx):
    if isinstance(node, ir.IRField):
        return _field(node, ctx)
    if isinstance(node, ir.IRParam):
        factory = ctx.locals.get(node.name)
        if factory is None:
            raise KeyError("unbound generic-constraint parameter %r" % node.name)
        return factory()
    if isinstance(node, ir.IRConstraintRef):
        return _ref_expr(node, ctx)
    if isinstance(node, ir.IRConst):
        # Match vsc.types.to_expr: int literals are signed, width 32.
        return ExprLiteralModel(node.value, True, 32)
    if isinstance(node, ir.IRBin):
        return ExprBinModel(_expr(node.lhs, ctx), _BIN[node.op], _expr(node.rhs, ctx))
    if isinstance(node, ir.IRUnary):
        if node.op == "~":
            return ExprUnaryModel(UnaryExprType.Not, _expr(node.operand, ctx))
        raise NotImplementedError("unary op %r" % node.op)
    if isinstance(node, ir.IRIndex):
        return _index(node, ctx)
    if isinstance(node, ir.IRPartSelect):
        # base[upper:lower] bit part-select (upper/lower resolve to constants).
        return ExprPartselectModel(_expr(node.base, ctx),
                                   _expr(node.upper, ctx), _expr(node.lower, ctx))
    if isinstance(node, ir.IRAttr):
        return _attr(node, ctx)
    if isinstance(node, ir.IRInside):
        return _inside(node, ctx)
    raise NotImplementedError("lower expr %r" % type(node).__name__)


def _attr(node, ctx):
    """Attribute access on an indexed/element base (composite-array element field
    or foreach element): self.arr[0].x, it.x."""
    base = _resolve_model(node.base, ctx)
    if isinstance(base, FieldArrayModel) and node.name == "sum":
        return ExprArraySumModel(base)
    return ExprFieldRefModel(_descend(base, node.name))


def _resolve_model(node, ctx):
    """Resolve an IRField/IRIndex/IRAttr access chain to a *concrete* FieldModel.
    Array subscripts must be constant (literal or unrolled-foreach index)."""
    if isinstance(node, ir.IRField):
        path = node.path
        head = path[0]
        if head in ctx.model_locals:
            model = ctx.model_locals[head]
        elif head in ctx.locals or head in ctx.const_locals:
            raise NotImplementedError(
                "cannot descend through scalar loop var %r" % head)
        else:
            model = ctx.model(head)
        if model is None:
            raise KeyError("constraint references unknown field %r" % head)
        for seg in path[1:]:
            model = _descend(model, seg)
        return model
    if isinstance(node, ir.IRAttr):
        return _descend(_resolve_model(node.base, ctx), node.name)
    if isinstance(node, ir.IRIndex):
        base = _resolve_model(node.base, ctx)
        if not isinstance(base, FieldArrayModel):
            raise TypeError("indexed access on a non-array model")
        return base.field_l[_const_index(node.index, ctx)]
    raise NotImplementedError("cannot resolve model for %r" % type(node).__name__)


def _descend(model, seg):
    if isinstance(model, FieldArrayModel):
        if seg == "size":
            return model.size
        raise NotImplementedError("array attribute %r in composite access" % seg)
    if isinstance(model, FieldCompositeModel):
        child = model.find_field(seg)
        if child is None:
            raise KeyError("composite %r has no field %r"
                           % (getattr(model, "name", "?"), seg))
        return child
    raise NotImplementedError(
        "cannot descend into %r at %r" % (seg, getattr(model, "name", "?")))


def _const_index(node, ctx):
    """Evaluate an array subscript that must resolve to a constant int."""
    if isinstance(node, ir.IRConst):
        return node.value
    if isinstance(node, ir.IRField) and len(node.path) == 1 \
            and node.path[0] in ctx.const_locals:
        return ctx.const_locals[node.path[0]]
    raise NotImplementedError(
        "composite-array subscripts must be constant (got %r)" % (node,))


def _field(node, ctx):
    path = node.path
    head = path[0]
    if head in ctx.locals:
        # Scalar foreach element/index: an expr binding.
        if len(path) == 1:
            return ctx.locals[head]()
        raise NotImplementedError("descent through foreach var %r" % (path,))
    if head in ctx.const_locals:
        # Unrolled-foreach index used as a value.
        if len(path) == 1:
            return ExprLiteralModel(ctx.const_locals[head], True, 32)
        raise NotImplementedError("descent through index var %r" % (path,))
    if head in ctx.model_locals:
        # Composite foreach element used directly (rare); descent goes via _attr.
        return ExprFieldRefModel(_resolve_model(node, ctx))
    model = ctx.model(head)
    if model is None:
        raise KeyError("constraint references unknown field %r" % head)
    # Walk the remaining path segments, descending through nested composites and
    # resolving array pseudo-attributes (arr.size / arr.sum).
    for seg in path[1:]:
        if isinstance(model, FieldArrayModel):
            if seg == "size":
                model = model.size
                continue
            if seg == "sum":
                return ExprArraySumModel(model)
            raise NotImplementedError("array attribute %r" % seg)
        if isinstance(model, FieldCompositeModel):
            child = model.find_field(seg)
            if child is None:
                raise KeyError("composite %r has no field %r" % (model.name, seg))
            model = child
            continue
        raise NotImplementedError("cannot descend into %r at %r" % (seg, model.name))
    return ExprFieldRefModel(model)


def _index(node, ctx):
    # Decide array-subscript vs scalar bit-select from the base's resolved model.
    base_model = None
    if isinstance(node.base, ir.IRField) and len(node.base.path) == 1:
        base_model = ctx.model(node.base.path[0])
    base_e = _expr(node.base, ctx)
    idx_e = _expr(node.index, ctx)
    if isinstance(base_model, FieldArrayModel):
        return ExprArraySubscriptModel(base_e, idx_e)
    return ExprPartselectModel(base_e, idx_e)


def _inside(node, ctx):
    lhs = _expr(node.lhs, ctx)
    rl = ExprRangelistModel()
    for r in node.ranges:
        # r.lo / r.hi are IR expr nodes (IRConst for literals, IRField for rand
        # endpoints, IRBin for arithmetic) — lower each so variable ranges work.
        if r.hi is None:
            rl.add_range(_expr(r.lo, ctx))
        else:
            rl.add_range(ExprRangeModel(_expr(r.lo, ctx), _expr(r.hi, ctx)))
    e = ExprInModel(lhs, rl)
    if node.negate:
        return ExprUnaryModel(UnaryExprType.Not, e)
    return e
