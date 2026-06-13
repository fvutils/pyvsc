"""
Constraint parser (Strategy A): compile a ``@vdc.constraint`` method to instance-
independent :mod:`vsc.dc.constraint_ir` — **once per type**, at decoration time.

It reads the method source (``inspect.getsource``), parses it with ``ast``, and
lowers the supported declarative subset into IR. The constraint body is *never
executed*; ``self.<field>`` becomes a symbolic :class:`IRField` keyed by name.

Supported in Phase 1: comparisons, arithmetic/bitwise binops, unary ``~``,
``self.x.inside(...)`` / ``not_inside`` / ``outside``, native ``if/else`` and
``with vdc.if_then()/else_if()/else_then`` and ``with vdc.implies()``, plus the
statement helpers ``vdc.soft()`` and ``vdc.unique()``.

Anything outside the grammar is rejected at decoration time with a file:line
pointer (see plan §6 risk 1) — better than silently capturing it.
"""
import ast
import inspect
import textwrap

from .constraint_ir import (ConstraintProgram, IRBin, IRConst, IRConstraintExpr,
                            IRDist, IRField, IRForeach, IRIfElse, IRImplies,
                            IRIndex, IRInside, IRRange, IRSoft, IRSolveOrder,
                            IRUnary, IRUnique, IRWeight)


class ConstraintParseError(Exception):
    pass


# AST binop/compare token -> IR op string (matches pyvsc's expr operators).
_BINOP = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "//",
    ast.FloorDiv: "//", ast.Mod: "%", ast.BitAnd: "&", ast.BitOr: "|",
    ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>",
}
_CMPOP = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=",
}

# Helper names recognized regardless of module prefix (vdc./vsc./bare).
_IFTHEN = "if_then"
_ELSEIF = "else_if"
_ELSETHEN = "else_then"
_IMPLIES = "implies"
_FOREACH = "foreach"


def parse_constraint(name, func):
    """Compile ``func`` (a constraint method) into a :class:`ConstraintProgram`.

    Raises :class:`ConstraintParseError` on unsupported syntax. Returns ``None``
    if source is unavailable (caller falls back / warns — plan §6 risk 2).
    """
    try:
        src = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError):
        return None

    mod = ast.parse(src)
    fn = mod.body[0]
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ConstraintParseError("constraint %r is not a function" % name)
    if not fn.args.args:
        raise ConstraintParseError("constraint %r must take self" % name)

    p = _Parser(name, fn.args.args[0].arg, func)
    stmts = p.parse_body(fn.body)
    return ConstraintProgram(name, stmts)


class _Parser:
    def __init__(self, cname, self_name, func):
        self.cname = cname
        self.self_name = self_name
        # Names bound by enclosing foreach loops (idx/it), referenceable as bare
        # Names in the body and resolved to IRField at lowering.
        self._bound = set()
        # Names visible to the constraint body (module globals + closure), used to
        # resolve enum members (MyEnum.A) and int constants to literals at parse time.
        self._names = dict(getattr(func, "__globals__", {}) or {})
        closure = getattr(func, "__closure__", None)
        freevars = getattr(getattr(func, "__code__", None), "co_freevars", ())
        if closure:
            for name, cell in zip(freevars, closure):
                try:
                    self._names[name] = cell.cell_contents
                except ValueError:
                    pass
        # For decent error locations: source file/line of the enclosing function.
        self.filename = getattr(getattr(func, "__code__", None), "co_filename", "?")
        self.lineno0 = getattr(getattr(func, "__code__", None), "co_firstlineno", 0)

    # -- errors --
    def _err(self, node, msg):
        line = self.lineno0 + getattr(node, "lineno", 1) - 1
        raise ConstraintParseError(
            "constraint %r (%s:%d): %s" % (self.cname, self.filename, line, msg))

    # -- statement bodies --
    def parse_body(self, body):
        out = []
        i = 0
        while i < len(body):
            stmt = body[i]
            node, consumed = self._parse_stmt(stmt, body, i)
            if node is not None:
                out.append(node)
            i += consumed
        return out

    def _parse_stmt(self, stmt, body, i):
        """Return (ir_node_or_None, num_siblings_consumed>=1)."""
        if isinstance(stmt, ast.Pass):
            return None, 1
        if isinstance(stmt, ast.Expr):
            return self._parse_expr_stmt(stmt.value), 1
        if isinstance(stmt, ast.If):
            return self._parse_native_if(stmt), 1
        if isinstance(stmt, ast.With):
            return self._parse_with(stmt, body, i)
        self._err(stmt, "unsupported statement %s (constraints are declarative)"
                  % type(stmt).__name__)

    def _parse_expr_stmt(self, value):
        # Statement-level helper calls: soft(...)/unique(...).
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            attr = value.func.attr
            if attr == "soft":
                if len(value.args) != 1:
                    self._err(value, "soft() takes exactly one expression")
                return IRSoft(self._expr(value.args[0]))
            if attr == "unique":
                return IRUnique([self._expr(a) for a in value.args])
            if attr == "solve_order":
                if len(value.args) != 2:
                    self._err(value, "solve_order(before, after) takes two arguments")
                return IRSolveOrder(self._field_list(value.args[0]),
                                    self._field_list(value.args[1]))
            if attr == "dist":
                if len(value.args) != 2:
                    self._err(value, "dist(lhs, [weight, ...]) takes two arguments")
                return IRDist(self._expr(value.args[0]),
                              self._parse_weights(value.args[1]))
            # inside/not_inside/outside fall through to expression handling.
        return IRConstraintExpr(self._expr(value))

    def _parse_native_if(self, stmt):
        cond = self._expr(stmt.test)
        true_body = self.parse_body(stmt.body)
        false_body = self.parse_body(stmt.orelse) if stmt.orelse else None
        return IRIfElse(cond, true_body, false_body)

    def _parse_with(self, stmt, body, i):
        if len(stmt.items) != 1:
            self._err(stmt, "with-statement must have a single context manager")
        ctx = stmt.items[0].context_expr
        attr = self._helper_name(ctx)
        if attr == _IMPLIES:
            cond = self._expr(self._helper_args(ctx)[0])
            return IRImplies(cond, self.parse_body(stmt.body)), 1
        if attr == _IFTHEN:
            cond = self._expr(self._helper_args(ctx)[0])
            node = IRIfElse(cond, self.parse_body(stmt.body), None)
            # Attach trailing else_if/else_then siblings.
            consumed = 1 + self._attach_else(node, body, i + 1)
            return node, consumed
        if attr == _FOREACH:
            return self._parse_foreach(stmt, ctx), 1
        if attr in (_ELSEIF, _ELSETHEN):
            self._err(stmt, "%s must directly follow if_then" % attr)
        self._err(stmt, "unsupported with-context %r" % (attr,))

    def _attach_else(self, if_node, body, j):
        """Greedily attach else_if/else_then siblings starting at index j.
        Returns the number of siblings consumed."""
        consumed = 0
        tail = if_node
        while j < len(body) and isinstance(body[j], ast.With) and len(body[j].items) == 1:
            ctx = body[j].items[0].context_expr
            attr = self._helper_name(ctx)
            if attr == _ELSEIF:
                cond = self._expr(self._helper_args(ctx)[0])
                nxt = IRIfElse(cond, self.parse_body(body[j].body), None)
                tail.false_body = [nxt]
                tail = nxt
                consumed += 1
                j += 1
            elif attr == _ELSETHEN:
                tail.false_body = self.parse_body(body[j].body)
                consumed += 1
                break
            else:
                break
        return consumed

    def _parse_foreach(self, stmt, ctx):
        args = self._helper_args(ctx)
        if not args:
            self._err(stmt, "foreach() requires the array as its first argument")
        array = self._expr(args[0])
        if not isinstance(array, IRField):
            self._err(stmt, "foreach() first argument must be an array field")

        # Resolve idx/it activation from kwargs, mirroring vsc.foreach defaults:
        # neither specified -> it only; otherwise unspecified ones default off.
        idx_kw = it_kw = None
        for kw in getattr(ctx, "keywords", []):
            if kw.arg == "idx":
                idx_kw = self._kwbool(kw.value)
            elif kw.arg == "it":
                it_kw = self._kwbool(kw.value)
        if idx_kw is None and it_kw is None:
            use_idx, use_it = False, True
        else:
            use_idx, use_it = bool(idx_kw), bool(it_kw)
        if not use_idx and not use_it:
            self._err(stmt, "foreach() with neither idx nor it is empty")

        # Bind the `as` target name(s).
        tgt = stmt.items[0].optional_vars
        idx_name = it_name = None
        if use_idx and use_it:
            if not (isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2):
                self._err(stmt, "foreach(idx=True, it=True) needs `as (idx, it)`")
            idx_name = tgt.elts[0].id
            it_name = tgt.elts[1].id
        elif use_idx:
            idx_name = tgt.id if isinstance(tgt, ast.Name) else self._err(
                stmt, "foreach(idx=True) needs a single `as` name")
        else:
            it_name = tgt.id if isinstance(tgt, ast.Name) else self._err(
                stmt, "foreach() needs a single `as` name")

        added = [n for n in (idx_name, it_name) if n is not None]
        self._bound.update(added)
        try:
            body = self.parse_body(stmt.body)
        finally:
            self._bound.difference_update(added)
        return IRForeach(array, idx_name, it_name, body)

    def _kwbool(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        self._err(node, "foreach idx/it must be a literal True/False")

    # -- helper-call introspection --
    def _helper_name(self, ctx):
        """Name of a constraint helper used as a context manager: handles
        ``vdc.if_then(c)`` (Call), ``vdc.else_then`` (Attribute) and
        ``vdc.else_then()`` (Call of Attribute)."""
        if isinstance(ctx, ast.Call):
            f = ctx.func
            return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if isinstance(ctx, ast.Attribute):
            return ctx.attr
        if isinstance(ctx, ast.Name):
            return ctx.id
        return None

    def _helper_args(self, ctx):
        if isinstance(ctx, ast.Call):
            return ctx.args
        return []

    # -- expressions --
    def _expr(self, node):
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.BinOp):
            op = _BINOP.get(type(node.op))
            if op is None:
                self._err(node, "unsupported binary operator")
            return IRBin(op, self._expr(node.left), self._expr(node.right))
        if isinstance(node, ast.BoolOp):
            self._err(node, "use '&'/'|' (not 'and'/'or') to combine constraints")
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Invert):
                return IRUnary("~", self._expr(node.operand))
            if isinstance(node.op, (ast.USub, ast.UAdd)):
                return IRConst(self._const(node))
            self._err(node, "use '~' (not 'not') for logical negation")
        if isinstance(node, ast.Call):
            return self._call_expr(node)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                self._err(node, "part-select slices in @constraint methods: not yet "
                          "supported (use randomize_with for bit-selects)")
            return IRIndex(self._expr(node.value), self._expr(node.slice))
        if isinstance(node, ast.Attribute):
            if self._is_self_rooted(node):
                return IRField(self._dotted(node))
            # e.g. MyEnum.A or module.CONST -> resolve to an int literal.
            return IRConst(self._resolve_external(node))
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return IRConst(int(node.value))
            if isinstance(node.value, int):
                return IRConst(node.value)
            self._err(node, "unsupported constant %r" % (node.value,))
        if isinstance(node, ast.Name):
            if node.id in self._bound:
                return IRField((node.id,))
            if node.id in self._names:
                return IRConst(self._as_int(node, self._names[node.id]))
            self._err(node, "reference to local/global %r not supported in constraints"
                      % node.id)
        self._err(node, "unsupported expression %s" % type(node).__name__)

    def _compare(self, node):
        if len(node.ops) == 1:
            op0 = node.ops[0]
            # 'x in rangelist{...}' / 'x not in {...}' -> inside.
            if isinstance(op0, (ast.In, ast.NotIn)):
                return IRInside(self._expr(node.left),
                                self._ranges(node.comparators[0]),
                                negate=isinstance(op0, ast.NotIn))
            op = _CMPOP.get(type(op0))
            if op is None:
                self._err(node, "unsupported comparison")
            return IRBin(op, self._expr(node.left), self._expr(node.comparators[0]))
        # Chained compare a<b<c  ->  (a<b) & (b<c)
        result = None
        left = node.left
        for cmp_op, right in zip(node.ops, node.comparators):
            op = _CMPOP.get(type(cmp_op))
            if op is None:
                self._err(node, "unsupported comparison")
            term = IRBin(op, self._expr(left), self._expr(right))
            result = term if result is None else IRBin("&", result, term)
            left = right
        return result

    def _call_expr(self, node):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in ("inside", "not_inside", "outside"):
                lhs = self._expr(node.func.value)
                if len(node.args) != 1:
                    self._err(node, "%s expects a single rangelist/list" % attr)
                ranges = self._ranges(node.args[0])
                return IRInside(lhs, ranges, negate=(attr != "inside"))
        self._err(node, "unsupported call in expression")

    def _ranges(self, node):
        """Parse the argument to inside(): vdc.rangelist(...) call, or a list."""
        if isinstance(node, ast.Call):
            items = node.args
        elif isinstance(node, (ast.List, ast.Tuple)):
            items = node.elts
        else:
            self._err(node, "inside() argument must be a rangelist(...) or list literal")
        out = []
        for it in items:
            if isinstance(it, ast.Tuple) and len(it.elts) == 2:
                out.append(IRRange(self._const(it.elts[0]), self._const(it.elts[1])))
            elif (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute)
                    and it.func.attr == "rng"):
                out.append(IRRange(self._const(it.args[0]), self._const(it.args[1])))
            elif isinstance(it, ast.List):
                for e in it.elts:
                    out.append(IRRange(self._const(e)))
            else:
                out.append(IRRange(self._const(it)))
        return out

    def _parse_weights(self, node):
        """Parse the weight-list argument of dist(): [vdc.weight(val, w[, per_value]), ...]."""
        if not isinstance(node, (ast.List, ast.Tuple)):
            self._err(node, "dist weights must be a list of vdc.weight(...) entries")
        out = []
        for w in node.elts:
            if not (isinstance(w, ast.Call) and isinstance(w.func, ast.Attribute)
                    and w.func.attr == "weight"):
                self._err(w, "each dist weight must be a vdc.weight(...) call")
            if len(w.args) != 2:
                self._err(w, "weight(val, w) takes a value/range and a weight")
            lo, hi = self._weight_val(w.args[0])
            weight = self._const(w.args[1])
            per_value = None
            for kw in w.keywords:
                if kw.arg == "per_value":
                    per_value = self._kwbool(kw.value)
            out.append(IRWeight(lo, hi, weight, per_value))
        return out

    def _weight_val(self, node):
        """A weight value: a single constant, a (lo, hi) tuple, or rng(lo, hi)."""
        if isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2:
            return self._const(node.elts[0]), self._const(node.elts[1])
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "rng"):
            return self._const(node.args[0]), self._const(node.args[1])
        return self._const(node), None

    def _field_list(self, node):
        """A solve_order argument: a single field ref or a list of field refs."""
        elts = node.elts if isinstance(node, (ast.List, ast.Tuple)) else [node]
        out = []
        for e in elts:
            fr = self._expr(e)
            if not isinstance(fr, IRField):
                self._err(e, "solve_order arguments must be field references")
            out.append(fr)
        return out

    def _is_self_rooted(self, node):
        cur = node
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        return isinstance(cur, ast.Name) and cur.id == self.self_name

    def _resolve_external(self, node):
        """Resolve a non-self attribute chain (e.g. MyEnum.A) from the constraint's
        visible names to an int literal."""
        attrs = []
        cur = node
        while isinstance(cur, ast.Attribute):
            attrs.insert(0, cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name):
            self._err(node, "unsupported attribute expression")
        if cur.id not in self._names:
            self._err(node, "name %r is not visible to the constraint" % cur.id)
        obj = self._names[cur.id]
        for a in attrs:
            try:
                obj = getattr(obj, a)
            except AttributeError:
                self._err(node, "%s has no attribute %r" % (cur.id, a))
        return self._as_int(node, obj)

    def _as_int(self, node, value):
        """Coerce a resolved external value (enum member or int) to its solver int.
        Enum members go through EnumInfo so plain (non-Int) enums map by index,
        matching the field's EnumFieldModel encoding."""
        import enum as _enum
        if isinstance(value, _enum.Enum):
            from vsc.impl.enum_info import EnumInfo
            return EnumInfo.get(type(value)).e2v(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            self._err(node, "constraint reference %r is not an integer/enum constant"
                      % (value,))

    def _dotted(self, node):
        """Return the attribute path tuple for self.a.b, verifying the root is self."""
        path = []
        cur = node
        while isinstance(cur, ast.Attribute):
            path.insert(0, cur.attr)
            cur = cur.value
        if not (isinstance(cur, ast.Name) and cur.id == self.self_name):
            self._err(node, "field reference must be rooted at '%s'" % self.self_name)
        return tuple(path)

    def _const(self, node):
        """Evaluate a constant int from an AST node: an int/bool literal, +/- of
        one, or an enum-member / global-constant reference (MyEnum.A, CONST)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, bool)):
            return int(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
            v = node.operand.value
            if isinstance(v, int):
                return -v if isinstance(node.op, ast.USub) else +v
        if isinstance(node, ast.Attribute):
            return self._resolve_external(node)
        if isinstance(node, ast.Name) and node.id in self._names:
            return self._as_int(node, self._names[node.id])
        self._err(node, "expected an integer/enum constant")
