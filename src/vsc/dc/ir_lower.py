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
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_unary_model import ExprUnaryModel
from vsc.model.field_array_model import FieldArrayModel
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

    def __init__(self, field_models):
        self.fields = field_models           # name -> FieldModel
        self.locals = {}                      # name -> callable() -> ExprModel

    def model(self, name):
        return self.fields.get(name)

    def with_local(self, name, factory):
        """Return a child Ctx with one extra local binding (foreach idx/elem)."""
        c = Ctx(self.fields)
        c.locals = dict(self.locals)
        if name is not None:
            c.locals[name] = factory
        return c


def lower_program(prog, field_models):
    """Build a fresh :class:`ConstraintBlockModel` from ``prog`` binding fields
    via ``field_models`` (name -> model)."""
    ctx = Ctx(field_models)
    block = ConstraintBlockModel(prog.name)
    for stmt in prog.stmts:
        block.constraint_l.append(_stmt(stmt, ctx))
    return block


def _stmt(node, ctx):
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
        weights.append(DistWeightExprModel(
            rng_lhs, rng_rhs, ExprLiteralModel(w.weight, True, 32),
            is_per_value=w.per_value))
    return ConstraintDistModel(lhs, weights)


def _foreach(node, ctx):
    arr = ctx.model(node.array.name)
    if not isinstance(arr, FieldArrayModel):
        raise TypeError("foreach target %r is not an array" % node.array.name)
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
    if isinstance(node, ir.IRInside):
        return _inside(node, ctx)
    raise NotImplementedError("lower expr %r" % type(node).__name__)


def _field(node, ctx):
    path = node.path
    if len(path) == 1:
        name = path[0]
        if name in ctx.locals:
            return ctx.locals[name]()
        model = ctx.model(name)
        if model is None:
            raise KeyError("constraint references unknown field %r" % name)
        return ExprFieldRefModel(model)
    if len(path) == 2:
        # array attribute access: arr.size / arr.sum
        arr = ctx.model(path[0])
        if isinstance(arr, FieldArrayModel):
            if path[1] == "size":
                return ExprFieldRefModel(arr.size)
            if path[1] == "sum":
                return ExprArraySumModel(arr)
        raise NotImplementedError(
            "dotted field path %r (nested objects land with composites)" % (path,))
    raise NotImplementedError("deep field path %r" % (path,))


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
        if r.hi is None:
            rl.add_range(ExprLiteralModel(r.lo, True, 32))
        else:
            rl.add_range(ExprRangeModel(
                ExprLiteralModel(r.lo, True, 32),
                ExprLiteralModel(r.hi, True, 32)))
    e = ExprInModel(lhs, rl)
    if node.negate:
        return ExprUnaryModel(UnaryExprType.Not, e)
    return e
