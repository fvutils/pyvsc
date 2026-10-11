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

from .constraint_ir import (ConstraintProgram, IRAttr, IRBin, IRClassConst,
                            IRCond, IRConst, IRReduce,
                            IRConstraintExpr, IRConstraintRef, IRDist, IRField,
                            IRForeach, IRIfElse, IRImplies, IRIndex, IRInside,
                            IRParam, IRPartSelect, IRRange, IRSoft, IRSolveOrder,
                            IRUnary, IRUnique, IRWeight, local_name)


class ConstraintParseError(Exception):
    pass


# AST binop/compare token -> IR op string (matches pyvsc's expr operators).
_BINOP = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
    ast.FloorDiv: "//", ast.Mod: "%", ast.BitAnd: "&", ast.BitOr: "|",
    ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>",
}
_CMPOP = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=",
}

_CMP_OPS = frozenset(_CMPOP.values())

# Constant collections a value set may name.
_COLLECTIONS = (list, tuple, set, frozenset, range)


class _Stepped:
    """``range(lo, hi, step)`` with a step other than 1, as a value-set entry."""

    def __init__(self, lo, hi, step):
        self.lo, self.hi, self.step = lo, hi, step

    def test(self, x):
        """``x in range(lo, hi, step)``."""
        if self.step > 0:
            lo, hi, k = self.lo, self.hi, self.step
            bounds = IRBin("&", IRBin("<=", lo, x), IRBin("<", x, hi))
            off = IRBin("-", x, lo)
        else:
            lo, hi, k = self.lo, self.hi, -self.step
            bounds = IRBin("&", IRBin("<", hi, x), IRBin("<=", x, lo))
            off = IRBin("-", lo, x)
        return IRBin("&", bounds, IRBin("==", IRBin("%", off, IRConst(k)),
                                        IRConst(0)))


# Most iterations a 'for' over a constant iterable unrolls to.
_MAX_UNROLL = 1024

# Largest exponent '**' expands into products.
_MAX_POW = 8

# Helper names recognized regardless of module prefix (vdc./vsc./bare).
_IFTHEN = "if_then"
_ELSEIF = "else_if"
_ELSETHEN = "else_then"
_IMPLIES = "implies"
_FOREACH = "foreach"


def parse_constraint(name, func, kind="fixed", arrays=frozenset(),
                     fields=frozenset()):
    """Compile ``func`` (a constraint method) into a :class:`ConstraintProgram`.

    ``kind`` is the marker set by the decorator: ``"fixed"`` (``@vdc.constraint``),
    ``"generic"`` (``@vdc.constraint.generic``) or ``"value"``
    (``@vdc.constraint.value``). ``arrays`` names the class's array fields. A
    method with parameters beyond ``self`` is forced
    to ``"generic"`` (a fixed constraint cannot bind parameters); a body that is a
    single ``return <expr>`` is a value generic.

    Raises :class:`ConstraintParseError` on unsupported syntax or when the
    method source cannot be read. Source is required because the constraint is
    compiled by parsing its AST, never by executing it; if the source is
    unavailable (e.g. the class was defined in a REPL / ``exec`` / ``python -c``)
    the constraint cannot be recovered. Silently dropping it would randomize the
    fields unconstrained — a wrong result with no error — so this is a hard
    failure rather than a warning.
    """
    try:
        src = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError) as e:
        raise ConstraintParseError(
            "cannot read source for constraint %r (defined in a REPL/exec/"
            "python -c?): the constraint is compiled from its source AST, so it "
            "cannot be applied. Define the class in an importable module file. "
            "(%s: %s)" % (name, type(e).__name__, e))

    mod = ast.parse(src)
    fn = mod.body[0]
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ConstraintParseError("constraint %r is not a function" % name)
    if not fn.args.args:
        raise ConstraintParseError("constraint %r must take self" % name)
    if fn.args.vararg is not None or fn.args.kwarg is not None:
        raise ConstraintParseError(
            "constraint %r: *args/**kwargs are not supported in a generic "
            "constraint signature" % name)

    # Formal parameters (everything past self), with any default values. Defaults
    # are concrete already-evaluated Python objects (via inspect.signature) — coerce
    # to int/enum literals, matching how constant references are lowered.
    sig_params = list(inspect.signature(func).parameters.values())[1:]
    params = tuple(sp.name for sp in sig_params)

    p = _Parser(name, fn.args.args[0].arg, func)
    p._params = set(params)
    p._arrays = arrays
    p._fields = fields
    p._src_lines = src.splitlines()

    param_defaults = {}
    for sp in sig_params:
        if sp.default is not inspect.Parameter.empty:
            param_defaults[sp.name] = IRConst(p._as_int(fn, sp.default))

    # A docstring documents the constraint; it is not part of it.
    body = [s for s in fn.body if not _is_string_stmt(s)]

    # Value generic: a single ``return <expr>`` body (or explicit @constraint.value).
    is_value = (kind == "value") or (
        len(body) == 1 and isinstance(body[0], ast.Return))
    if is_value:
        if not (len(body) == 1 and isinstance(body[0], ast.Return)
                and body[0].value is not None):
            raise ConstraintParseError(
                "constraint %r: a value generic must be a single 'return <expr>'"
                % name)
        ret = p._expr(body[0].value)
        return ConstraintProgram(name, [], kind="value", params=params, ret=ret,
                                 param_defaults=param_defaults)

    stmts = p.parse_body(body)
    eff_kind = "generic" if (params and kind == "fixed") else kind
    return ConstraintProgram(name, stmts, kind=eff_kind, params=params,
                             param_defaults=param_defaults)


# Builtins a constraint expression may call (when not shadowed).
_BUILTINS = frozenset(("abs", "all", "any", "bool", "len", "max", "min",
                       "sum"))

# The loops a generator (and, later, a 'for' statement) may run over an array.
_LOOP_FORMS = ("'for x in self.arr', 'for i in range(len(self.arr))' or "
               "'for i, x in enumerate(self.arr)'")


_CONST_OPS = {"+": int.__add__, "-": int.__sub__, "*": int.__mul__}


def _const_value(e):
    """The value of ``e`` when it is a constant (+, -, * of literals), else
    None."""
    if isinstance(e, IRConst):
        return int(e.value)
    if isinstance(e, IRBin) and e.op in _CONST_OPS:
        a, b = _const_value(e.lhs), _const_value(e.rhs)
        if a is not None and b is not None:
            return _CONST_OPS[e.op](a, b)
    return None


def _is_bool(e):
    """True when IR expression ``e`` is a truth value (0 or 1)."""
    if isinstance(e, IRBin):
        if e.op in _CMP_OPS:
            return True
        if e.op in ("&", "|", "^"):
            return _is_bool(e.lhs) and _is_bool(e.rhs)
        return False
    if isinstance(e, IRInside):
        return True
    if isinstance(e, IRCond):
        return _is_bool(e.t) and _is_bool(e.f)
    return isinstance(e, IRConst) and e.value in (0, 1)


def _bool(e):
    """``e`` as a truth value: itself when it already is one, else ``e != 0``.

    ``~b`` of a truth value ``b`` is taken as ``not b``, as it is in a
    statement. Compared with 0 it would be widened first, and the invert of a
    widened 0 or 1 is never 0."""
    if _is_bool(e):
        return e
    if isinstance(e, IRUnary) and e.op == "~" and _is_bool(e.operand):
        return IRBin("==", e.operand, IRConst(0))
    return IRBin("!=", e, IRConst(0))


def _is_string_stmt(stmt):
    """A bare string statement, such as a docstring."""
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


class _Parser:
    def __init__(self, cname, self_name, func):
        self.cname = cname
        self.self_name = self_name
        # Formal parameter names of a generic constraint (set by parse_constraint
        # after construction); a bare Name matching one lowers to IRParam.
        self._params = set()
        # Names of the class's fields, and of its array fields (``self.<name>``).
        self._fields = frozenset()
        self._arrays = frozenset()
        # Lines of the (dedented) source the AST was parsed from, used where the
        # AST drops a detail (parentheses).
        self._src_lines = None
        # Names bound by enclosing foreach loops (idx/it), referenceable as bare
        # Names in the body and resolved to IRField at lowering.
        self._bound = set()
        # Names bound by an unrolled constant 'for' to the current value.
        self._loop_consts = {}
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
        # The name of the class the method is defined in ('T' of 'T.c').
        parts = getattr(func, "__qualname__", "").split(".")
        self.own_class = parts[-2] if len(parts) >= 2 and parts[-2] != "<locals>" \
            else None
        # For decent error locations: source file/line of the enclosing function.
        self.filename = getattr(getattr(func, "__code__", None), "co_filename", "?")
        self.lineno0 = getattr(getattr(func, "__code__", None), "co_firstlineno", 0)

    # -- errors --
    def _err(self, node, msg):
        line = self.lineno0 + getattr(node, "lineno", 1) - 1
        raise ConstraintParseError(
            "constraint %r (%s:%d): %s" % (self.cname, self.filename, line, msg))

    def _where(self, node):
        """``(file:line)`` of ``node``, for an error raised after parsing."""
        return "(%s:%d)" % (self.filename, self._abs_line(node))

    def _is_own_class_attr(self, node):
        """``T.NAME``, ``T`` being the class this constraint is defined in.
        (``T`` is not bound yet when the class is decorated.)"""
        return (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == self.own_class)

    def _abs_line(self, node):
        """Absolute source line of ``node`` (for deferred decoration-time errors
        raised after the AST line context is gone, e.g. reference validation)."""
        return self.lineno0 + getattr(node, "lineno", 1) - 1

    # -- statement bodies --
    def parse_body(self, body):
        out = []
        i = 0
        while i < len(body):
            stmt = body[i]
            node, consumed = self._parse_stmt(stmt, body, i)
            if isinstance(node, list):
                out.extend(node)            # an unrolled constant 'for'
            elif node is not None:
                out.append(node)
            i += consumed
        return out

    def _parse_stmt(self, stmt, body, i):
        """Return (ir_node_or_None, num_siblings_consumed>=1)."""
        if isinstance(stmt, ast.Pass) or _is_string_stmt(stmt):
            return None, 1
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            v = stmt.value.value
            if v is Ellipsis:
                return None, 1              # '...': a placeholder, like pass
            if not isinstance(v, bool):
                self._err(stmt, "a bare constant %r is not a constraint; "
                                "only True (no-op) and False (unsatisfiable) "
                                "are" % (v,))
        if isinstance(stmt, ast.Expr):
            return self._parse_expr_stmt(stmt.value), 1
        if isinstance(stmt, ast.If):
            return self._parse_native_if(stmt), 1
        if isinstance(stmt, ast.For):
            return self._parse_for(stmt), 1
        if isinstance(stmt, getattr(ast, "Match", ())):
            return self._parse_match(stmt), 1
        if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            self._assignment(stmt)
        if isinstance(stmt, ast.Assert):
            self._err(stmt, "'assert' is not a constraint; write the condition "
                            "alone: '%s'" % ast.unparse(stmt.test))
        if isinstance(stmt, (ast.Break, ast.Continue)):
            self._err(stmt, "'%s' has no meaning in a constraint loop: every "
                            "iteration's constraints hold; guard them with "
                            "'if'" % type(stmt).__name__.lower())
        if isinstance(stmt, ast.With):
            return self._parse_with(stmt, body, i)
        self._err(stmt, "unsupported statement %s (constraints are declarative)"
                  % type(stmt).__name__)

    def _parse_expr_stmt(self, value):
        # A statement 'a and b' or 'lo < x < hi' is several statements: the
        # same meaning, and each part is seen on its own (a size bound in
        # '1 < len(self.arr) < 4' then bounds the array).
        if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.And):
            # Each part keeps its meaning as an operand ('self.ON' is a class
            # constant here, not a generic-constraint reference).
            out = []
            for v in value.values:
                if (isinstance(v, ast.BoolOp) and isinstance(v.op, ast.And)
                        or isinstance(v, ast.Compare) and len(v.ops) > 1):
                    out.extend(self._parse_expr_stmt(v))
                else:
                    out.append(IRConstraintExpr(_bool(self._expr(v))))
            return out
        if isinstance(value, ast.Compare) and len(value.ops) > 1:
            self._check_chain_operands(value)
            out = []
            left = value.left
            for op, right in zip(value.ops, value.comparators):
                part = ast.copy_location(
                    ast.Compare(left=left, ops=[op], comparators=[right]), value)
                out.append(IRConstraintExpr(self._compare(part)))
                left = right
            return out
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
            # A generic-constraint reference: self.<name>(...) directly on self
            # (a field method like self.x.inside() has an Attribute, not Name, base).
            if (isinstance(value.func.value, ast.Name)
                    and value.func.value.id == self.self_name
                    and attr not in ("inside", "not_inside", "outside")):
                return self._constraint_ref(value, attr, value.args, value.keywords)
            # inside/not_inside/outside fall through to expression handling.
        # A bare ``self.<name>`` statement: a field is tested for truth (G-68),
        # anything else references a generic constraint.
        if (isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == self.self_name):
            if value.attr in self._arrays:
                self._err(value, "an array is not a constraint; constrain its "
                                 "elements or its .size")
            if value.attr in self._fields:
                return IRConstraintExpr(IRField((value.attr,)))
            return IRConstraintRef(value.attr, [], self._abs_line(value))
        if (isinstance(value, ast.Call) and self._builtin(value) == "all"
                and len(value.args) == 1
                and isinstance(value.args[0], ast.GeneratorExp)):
            # all(...) as a statement is a foreach.
            array, idx, it, cond, filt = self._generator(value, value.args[0])
            body = IRConstraintExpr(cond)
            if filt is not None:
                body = IRImplies(filt, [body])
            return IRForeach(array, idx, it, [body])
        if isinstance(value, ast.IfExp):
            # 't if c else f' as a statement is 'if c: t else: f'.
            return IRIfElse(self._expr(value.test),
                            [IRConstraintExpr(_bool(self._expr(value.body)))],
                            [IRConstraintExpr(_bool(self._expr(value.orelse)))])
        return IRConstraintExpr(self._expr(value))

    def _constraint_ref(self, node, name, args, keywords):
        """Build an IRConstraintRef from a ``self.<name>(actuals...)`` reference,
        capturing positional and keyword actuals (bound to formals at lowering)."""
        kw_irs = {}
        for kw in keywords:
            if kw.arg is None:
                self._err(node, "**-unpacking is not supported in a "
                          "generic-constraint reference")
            kw_irs[kw.arg] = self._expr(kw.value)
        return IRConstraintRef(name, [self._expr(a) for a in args],
                               self._abs_line(node), kw_irs)

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

    def _parse_match(self, stmt):
        """``match``/``case`` as an if/elif chain. A case pattern is a literal,
        a dotted constant (``E.A``), an or-pattern of those, or ``_``; the
        first matching case applies, and no match constrains nothing."""
        subject = self._expr(stmt.subject)
        chain = []                  # (cond or None for '_', body)
        for case in stmt.cases:
            if case.guard is not None:
                self._err(case.guard, "a case guard ('if') is not supported in "
                                      "a constraint; nest an 'if' in the body")
            values = self._case_values(case.pattern)
            cond = None if values is None else (
                IRBin("==", subject, values[0]) if len(values) == 1
                else IRInside(subject, [IRRange(v) for v in values]))
            chain.append((cond, self.parse_body(case.body)))
        out = None
        for cond, body in reversed(chain):
            if cond is None:
                out = body
            else:
                out = [IRIfElse(cond, body, out)]
        return out

    def _case_values(self, pat):
        """The values a case pattern matches, or None for '_'."""
        if isinstance(pat, ast.MatchAs) and pat.pattern is None and pat.name is None:
            return None
        if isinstance(pat, ast.MatchOr):
            vals = []
            for p in pat.patterns:
                v = self._case_values(p)
                if v is None:
                    self._err(p, "'_' inside an or-pattern is not supported")
                vals.extend(v)
            return vals
        if isinstance(pat, ast.MatchSingleton) and isinstance(pat.value, bool):
            return [IRConst(int(pat.value))]
        if isinstance(pat, ast.MatchValue):
            v = self._expr(pat.value)
            if isinstance(v, (IRConst, IRClassConst)):
                return [v]
        if isinstance(pat, ast.MatchAs):
            self._err(pat, "a capture pattern binds a name; match a value: a "
                           "literal or a dotted constant such as E.A")
        self._err(pat, "a case pattern in a constraint is a literal, a dotted "
                       "constant (E.A), an or-pattern of those, or '_'")

    def _assignment(self, stmt):
        """Reject an assignment with what was probably meant."""
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if all(isinstance(t, ast.Name) for t in targets):
            self._err(stmt, "local variables are not supported in a constraint; "
                            "write the expression where it is used")
        if isinstance(stmt, ast.Assign) and len(targets) == 1:
            self._err(stmt, "a constraint is not an assignment; did you mean "
                            "'%s == %s'?" % (ast.unparse(targets[0]),
                                             ast.unparse(stmt.value)))
        self._err(stmt, "a constraint is not an assignment: its body is not "
                        "executed; state the relation with '==', '<', ...")

    def _parse_for(self, stmt):
        """``for`` over an array field: a foreach (forms in _LOOP_FORMS). Over
        a constant iterable: the body once per value, unrolled here."""
        if stmt.orelse:
            self._err(stmt, "a constraint 'for' has no 'else'")
        values = self._const_iterable(stmt.iter)
        if values is not None:
            return self._unroll(stmt, values)
        array, idx, it = self._loop(stmt, stmt.target, stmt.iter)
        saved = set(self._bound)
        self._bound.update(n for n in (idx, it) if n is not None)
        try:
            body = self.parse_body(stmt.body)
        finally:
            self._bound = saved
        return IRForeach(array, idx, it, body)

    def _const_iterable(self, it):
        """The values of a constant ``range(...)`` or named collection, or
        None when ``it`` is not one."""
        if self._is_builtin_call(it, "range") and not it.keywords \
                and 1 <= len(it.args) <= 3:
            args = [_const_value(self._expr(a)) for a in it.args]
            if all(a is not None for a in args) and (len(args) < 3 or args[2]):
                return list(range(*args))
            return None
        if isinstance(it, (ast.List, ast.Tuple, ast.Set)):
            vals = [self._const_literal(e) for e in it.elts]
            return None if any(v is None for v in vals) else vals
        coll = self._const_collection(it)
        if coll is None:
            return None
        if isinstance(coll, (set, frozenset)):
            coll = sorted(coll, key=repr)
        return list(coll)

    def _const_literal(self, node):
        """A constant element of a literal iterable: an int or enum constant,
        or a tuple of them. None otherwise."""
        if isinstance(node, ast.Tuple):
            vals = [self._const_literal(e) for e in node.elts]
            return None if any(v is None for v in vals) else tuple(vals)
        if isinstance(node, (ast.Constant, ast.Attribute, ast.Name,
                             ast.UnaryOp, ast.BinOp)) \
                and not self._is_self_rooted(node):
            try:
                return _const_value(self._expr(node))
            except ConstraintParseError:
                return None
        return None

    def _unroll(self, stmt, values):
        if len(values) > _MAX_UNROLL:
            self._err(stmt, "a constant 'for' unrolls to at most %d iterations"
                            % _MAX_UNROLL)
        tgt = stmt.target
        if isinstance(tgt, ast.Name):
            names = [tgt.id]
        elif (isinstance(tgt, ast.Tuple)
                and all(isinstance(e, ast.Name) for e in tgt.elts)):
            names = [e.id for e in tgt.elts]
        else:
            self._err(stmt, "a constant 'for' binds a name or a tuple of names")
        out = []
        saved = dict(self._loop_consts)
        try:
            for v in values:
                vs = (v,) if len(names) == 1 else v
                if not isinstance(vs, (tuple, list)) or len(vs) != len(names):
                    self._err(stmt, "cannot unpack %r into %d names"
                                    % (v, len(names)))
                for n, x in zip(names, vs):
                    self._loop_consts[n] = self._as_int(stmt, x)
                out.extend(self.parse_body(stmt.body))
        finally:
            self._loop_consts = saved
        return out

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
            if isinstance(node.op, ast.Div):
                self._err(node, "integer constraints have no true division; "
                                "use '//'")
            if isinstance(node.op, ast.Pow):
                return self._pow(node)
            if op is None:
                self._err(node, "unsupported binary operator")
            return IRBin(op, self._expr(node.left), self._expr(node.right))
        if isinstance(node, ast.BoolOp):
            # Logical: each operand is tested for truth. Python's short-circuit
            # and value-returning semantics do not apply.
            op = "&" if isinstance(node.op, ast.And) else "|"
            terms = [_bool(self._expr(v)) for v in node.values]
            result = terms[0]
            for t in terms[1:]:
                result = IRBin(op, result, t)
            return result
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Invert):
                return IRUnary("~", self._expr(node.operand))
            if isinstance(node.op, ast.Not):
                # Not '~': that inverts every bit of a wide operand.
                return IRBin("==", _bool(self._expr(node.operand)), IRConst(0))
            if isinstance(node.op, ast.UAdd):
                return self._expr(node.operand)
            if isinstance(node.op, ast.USub):
                # '0 - x': the 32-bit literal widens the result, so it keeps
                # Python's value (a u8 'a' gives -a in [-255, 0], never 0xFF).
                o = self._expr(node.operand)
                if isinstance(o, IRConst):
                    return IRConst(-o.value)
                return IRBin("-", IRConst(0), o)
        if isinstance(node, ast.IfExp):
            c = _bool(self._expr(node.test))
            t, f = self._expr(node.body), self._expr(node.orelse)
            if _is_bool(t) and _is_bool(f):
                # Logic, not a 1-bit select: dv-solve draws a 1-bit select's
                # condition unevenly.
                return IRBin("|", IRBin("&", c, t),
                             IRBin("&", IRBin("==", c, IRConst(0)), f))
            return IRCond(c, t, f)
        if isinstance(node, ast.Call):
            return self._call_expr(node)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                if self._is_array(node.value):
                    self._err(node, "array slices are not supported in "
                                    "constraints; index one element or use "
                                    "a foreach")
                sl = node.slice
                if sl.step is not None:
                    self._err(node, "part-select with a step (a[hi:lo:step]) is not supported")
                if sl.lower is None or sl.upper is None:
                    self._err(node, "part-select requires explicit bounds a[hi:lo]")
                # Source `a[hi:lo]` -> AST slice.lower=hi (pyvsc upper bit),
                # slice.upper=lo (pyvsc lower bit).
                hi, lo = self._expr(sl.lower), self._expr(sl.upper)
                hv, lv = _const_value(hi), _const_value(lo)
                if hv is not None and lv is not None and hv < lv:
                    self._err(node, "a part-select is [hi:lo], high bit first "
                                    "(SV order): write [%d:%d]" % (lv, hv))
                return IRPartSelect(self._expr(node.value), hi, lo)
            return IRIndex(self._expr(node.value), self._expr(node.slice))
        if isinstance(node, ast.Attribute):
            if self._is_self_rooted(node):
                return IRField(self._dotted(node))
            # Attribute over an indexed/local base (composite-array element or
            # foreach element): self.arr[0].x, it.x -> IRAttr.
            root = self._root_name(node)
            if isinstance(root, ast.Name) and (
                    root.id == self.self_name or root.id in self._bound):
                return IRAttr(self._expr(node.value), node.attr)
            if self._is_own_class_attr(node):
                return IRClassConst(node.attr, self._where(node))
            # e.g. MyEnum.A or module.CONST -> resolve to an int literal.
            return IRConst(self._resolve_external(node))
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return IRConst(int(node.value))
            if isinstance(node.value, int):
                return IRConst(node.value)
            self._err(node, "unsupported constant %r" % (node.value,))
        if isinstance(node, ast.Name):
            if node.id in self._loop_consts:
                return IRConst(self._loop_consts[node.id])
            if node.id in self._params:
                # A generic-constraint formal — bound to its actual at the ref site.
                return IRParam(node.id)
            if node.id in self._bound:
                return IRField((local_name(node.id),))
            if node.id in self._names:
                return IRConst(self._as_int(node, self._names[node.id]))
            self._err(node, "reference to local/global %r not supported in constraints"
                      % node.id)
        self._err(node, "unsupported expression %s" % type(node).__name__)

    def _pow(self, node):
        """``x ** k`` for a constant ``k`` in 0..8, as products of ``x``."""
        k = self._expr(node.right)
        if not (isinstance(k, IRConst) and 0 <= k.value <= _MAX_POW):
            self._err(node, "'**' needs a constant exponent from 0 to %d"
                            % _MAX_POW)
        x = self._expr(node.left)
        if isinstance(x, IRConst):
            return IRConst(x.value ** k.value)

        def power(n):
            if n == 1:
                return x
            half = power(n // 2)
            sq = IRBin("*", half, half)
            return IRBin("*", sq, x) if n % 2 else sq
        return power(k.value) if k.value else IRConst(1)

    def _compare(self, node):
        if len(node.ops) == 1:
            op0 = node.ops[0]
            # 'x in rangelist{...}' / 'x not in {...}' -> inside.
            if isinstance(op0, (ast.In, ast.NotIn)):
                return self._membership(self._expr(node.left),
                                        self._ranges(node.comparators[0]),
                                        isinstance(op0, ast.NotIn))
            op = _CMPOP.get(type(op0))
            if op is None:
                self._err(node, "unsupported comparison")
            return IRBin(op, self._expr(node.left), self._expr(node.comparators[0]))
        # Chained compare a<b<c  ->  (a<b) & (b<c)
        self._check_chain_operands(node)
        result = None
        left = node.left
        for cmp_op, right in zip(node.ops, node.comparators):
            if isinstance(cmp_op, (ast.In, ast.NotIn)):
                term = self._membership(self._expr(left), self._ranges(right),
                                        isinstance(cmp_op, ast.NotIn))
                result = term if result is None else IRBin("&", result, term)
                left = right
                continue
            op = _CMPOP.get(type(cmp_op))
            if op is None:
                self._err(node, "unsupported comparison")
            term = IRBin(op, self._expr(left), self._expr(right))
            result = term if result is None else IRBin("&", result, term)
            left = right
        return result

    def _check_chain_operands(self, node):
        """Reject ``a > 3 & a < 6``: '&' binds tighter than '>', so Python reads
        it as the chain ``a > (3 & a) < 6``. A parenthesized operand
        (``a < (b & c) < d``) is taken as meant."""
        for cmp_op, opnd in zip(node.ops, node.comparators):
            if (isinstance(opnd, ast.BinOp)
                    and isinstance(opnd.op, (ast.BitAnd, ast.BitOr, ast.BitXor))
                    and not self._parenthesized(opnd)):
                self._err(node, "'%s' binds tighter than '%s', so this is a "
                          "chained comparison; write (x > 3) and (x < 6), or "
                          "parenthesize each comparison: (x > 3) & (x < 6)"
                          % (_BINOP[type(opnd.op)],
                             _CMPOP.get(type(cmp_op), "in")))

    def _parenthesized(self, node):
        """True when ``node`` is written in parentheses. The AST drops them, but
        a node's position excludes them, so look at the source just before it."""
        if self._src_lines is None:
            return True
        ln, col = node.lineno - 1, node.col_offset
        while ln >= 0:
            line = self._src_lines[ln].encode()     # col_offset is in bytes
            text = line[:col].decode(errors="replace").rstrip()
            if text.endswith("\\"):
                text = text[:-1].rstrip()
            if text:
                return text.endswith("(")
            ln -= 1
            col = None
        return False

    def _call_expr(self, node):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in ("inside", "not_inside", "outside"):
                lhs = self._expr(node.func.value)
                if len(node.args) != 1:
                    self._err(node, "%s expects a single rangelist/list" % attr)
                return self._membership(lhs, self._ranges(node.args[0]),
                                        attr != "inside")
            # A generic-constraint reference used as a boolean/value term:
            # self.<name>(...) directly on self.
            if (isinstance(node.func.value, ast.Name)
                    and node.func.value.id == self.self_name):
                return self._constraint_ref(node, attr, node.args, node.keywords)
        builtin = self._builtin(node)
        if builtin is not None:
            return self._builtin_call(node, builtin)
        if self._is_math_prod(node.func):
            if len(node.args) != 1 or node.keywords:
                self._err(node, "math.prod() in a constraint takes one array")
            return self._array_reduction(node, node.args[0], "product",
                                         "math.prod")
        self._err(node, "unsupported call in expression")

    def _is_math_prod(self, func):
        """``math.prod`` (or ``prod`` imported from it)."""
        import math
        if isinstance(func, ast.Attribute):
            return (func.attr == "prod" and isinstance(func.value, ast.Name)
                    and self._names.get(func.value.id) is math)
        return (isinstance(func, ast.Name) and func.id not in self._params
                and func.id not in self._bound
                and self._names.get(func.id) is math.prod)

    def _array_reduction(self, node, arg, attr, name):
        """``len``/``sum``/``math.prod`` of ``self.<array>``: its ``.size``,
        ``.sum`` or ``.product``."""
        if not self._is_array(arg):
            self._err(node, "%s() in a constraint takes an array field "
                            "(self.<array>)" % name)
        return IRField(self._dotted(arg) + (attr,))

    def _builtin(self, node):
        """The name of the builtin ``node`` calls, or None. A name the
        function's globals, closure, parameters or a loop rebinds is not the
        builtin."""
        f = node.func
        if (isinstance(f, ast.Name) and f.id in _BUILTINS
                and f.id not in self._names and f.id not in self._params
                and f.id not in self._bound):
            return f.id
        return None

    def _is_builtin_call(self, node, name):
        """``node`` calls builtin ``name`` (not a rebound name)."""
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == name and name not in self._names
                and name not in self._params and name not in self._bound)

    def _loop_forms(self):
        """_LOOP_FORMS, spelled with this body's name for ``self``."""
        return _LOOP_FORMS.replace("self.", self.self_name + ".")

    def _loop(self, node, target, it):
        """The array and loop names of ``for <target> in <it>``: ``(array,
        idx_name, it_name)``. Only the forms in _LOOP_FORMS."""
        if isinstance(target, ast.Name) and self._is_builtin_call(it, "range") \
                and len(it.args) == 1 and not it.keywords:
            n = it.args[0]
            if self._is_builtin_call(n, "len") and len(n.args) == 1:
                return self._loop_array(node, n.args[0]), target.id, None
            if isinstance(n, ast.Attribute) and n.attr == "size":
                return self._loop_array(node, n.value), target.id, None
        elif isinstance(target, ast.Name):
            return self._loop_array(node, it), None, target.id
        elif (isinstance(target, ast.Tuple) and len(target.elts) == 2
                and all(isinstance(e, ast.Name) for e in target.elts)
                and self._is_builtin_call(it, "enumerate")
                and len(it.args) == 1 and not it.keywords):
            return (self._loop_array(node, it.args[0]), target.elts[0].id,
                    target.elts[1].id)
        self._err(node, "a constraint loop runs over an array field: %s"
                        % self._loop_forms())

    def _loop_array(self, node, arr):
        array = self._expr(arr) if isinstance(arr, ast.Attribute) else None
        if not isinstance(array, IRField) or (
                len(array.path) == 1 and array.path[0] not in self._arrays):
            self._err(node, "a constraint loop runs over an array field: %s"
                            % self._loop_forms())
        return array

    def _generator(self, node, gen):
        """``(array, idx_name, it_name, cond, filt)`` of an ``all``/``any``
        generator: one ``for`` over an array, with optional ``if``s."""
        if len(gen.generators) != 1 or gen.generators[0].is_async:
            self._err(node, "a generator in a constraint has one 'for' over "
                            "an array: %s" % self._loop_forms())
        comp = gen.generators[0]
        array, idx, it = self._loop(node, comp.target, comp.iter)
        saved = set(self._bound)
        self._bound.update(n for n in (idx, it) if n is not None)
        try:
            cond = _bool(self._expr(gen.elt))
            filt = None
            for f in comp.ifs:
                t = _bool(self._expr(f))
                filt = t if filt is None else IRBin("&", filt, t)
        finally:
            self._bound = saved
        return array, idx, it, cond, filt

    def _builtin_call(self, node, name):
        if node.keywords:
            self._err(node, "%s() in a constraint takes no keyword arguments"
                            % name)
        args = node.args
        if any(isinstance(a, ast.Starred) for a in args):
            self._err(node, "%s() in a constraint takes no *arguments" % name)
        if name in ("all", "any"):
            if len(args) != 1 or not isinstance(args[0], ast.GeneratorExp):
                self._err(node, "%s() in a constraint takes a generator over an "
                                "array: %s(<cond> for x in self.arr)"
                                % (name, name))
            array, idx, it, cond, filt = self._generator(node, args[0])
            return IRReduce(name, array, idx, it, cond, filt)
        if name in ("len", "sum"):
            if len(args) != 1:
                self._err(node, "%s() in a constraint takes one array" % name)
            return self._array_reduction(node, args[0],
                                         "size" if name == "len" else "sum",
                                         name)
        if name in ("min", "max") and len(args) == 1 and self._is_array(args[0]):
            self._err(node, "%s() over an array is not supported yet; use a "
                            "foreach with an auxiliary field" % name)
        if name in ("abs", "bool"):
            if len(args) != 1:
                self._err(node, "%s() takes one argument" % name)
            x = self._expr(args[0])
            if name == "bool":
                return _bool(x)
            return IRCond(IRBin("<", x, IRConst(0)), IRBin("-", IRConst(0), x), x)
        # min / max
        if len(args) < 2:
            self._err(node, "scalar %s() needs two or more arguments" % name)
        op = "<" if name == "min" else ">"
        terms = [self._expr(a) for a in args]
        result = terms[0]
        for t in terms[1:]:
            # Python keeps the first of equal values; they are equal anyway.
            result = IRCond(IRBin(op, t, result), t, result)
        return result

    @staticmethod
    def _callee_name(node):
        """Bare name of a call target: ``rangelist``/``vdc.rangelist`` -> 'rangelist'."""
        f = node.func
        if isinstance(f, ast.Attribute):
            return f.attr
        if isinstance(f, ast.Name):
            return f.id
        return None

    def _range_call(self, node):
        """``range(hi)`` / ``range(lo, hi)`` -> a HALF-OPEN IRRange, i.e. [lo, hi-1].

        Half-open because that is what ``range`` means in Python: ``a in range(3, 50)``
        must exclude 50, exactly as ``50 in range(3, 50)`` is False. The inclusive
        spellings are ``(lo, hi)``, ``vdc.rng(lo, hi)`` and ``vdc.r[lo:hi]``.

        A literal upper bound is decremented at parse time; a non-literal one becomes
        ``hi - 1`` so field/arithmetic endpoints keep working.
        """
        if len(node.args) == 1:
            lo, hi = IRConst(0), self._expr(node.args[0])
        elif len(node.args) in (2, 3):
            lo, hi = self._expr(node.args[0]), self._expr(node.args[1])
        else:
            self._err(node, "range() takes 1 to 3 arguments")
        if len(node.args) == 3:
            step = self._expr(node.args[2])
            if not isinstance(step, IRConst) or step.value == 0:
                self._err(node, "range() step must be a non-zero constant")
            if step.value != 1:
                return _Stepped(lo, hi, step.value)
        if isinstance(hi, IRConst):
            hi = IRConst(hi.value - 1)
        else:
            hi = IRBin("-", hi, IRConst(1))
        return IRRange(lo, hi)

    def _slice_range(self, sl):
        """``vdc.r[lo:hi]`` -> an INCLUSIVE IRRange [lo, hi], matching SystemVerilog
        ``inside {[lo:hi]}``. (Contrast ``range(lo, hi)``, which is half-open.)"""
        if sl.step is not None:
            self._err(sl, "a range slice with a step (r[lo:hi:step]) is not supported")
        if sl.lower is None or sl.upper is None:
            self._err(sl, "a range slice requires explicit bounds (r[lo:hi])")
        return IRRange(self._expr(sl.lower), self._expr(sl.upper))

    def _ranges(self, node):
        """Parse the argument to ``inside()`` / the RHS of ``in``.

        Accepted forms (all denote a set of values):

          * ``vdc.rangelist(...)``       -- classic spelling
          * ``[...]`` / ``(...)``        -- list/tuple literal
          * ``range(lo, hi)``            -- HALF-OPEN, Python semantics
          * ``vdc.r[lo:hi]``             -- INCLUSIVE, SystemVerilog semantics

        and, as elements of a list: a bare value, a ``(lo, hi)`` tuple (inclusive),
        ``vdc.rng(lo, hi)`` (inclusive), ``range(lo, hi)`` (half-open), or a nested
        list of values.
        """
        if isinstance(node, ast.Call):
            callee = self._callee_name(node)
            if callee == "range":
                return [self._range_call(node)]
            if callee != "rangelist":
                # Historically ANY call had its arguments splatted as set members,
                # so `a in range(3, 50)` silently meant `a inside {3, 50}`. Refuse
                # unrecognized calls rather than guess at their arguments.
                self._err(node, "unsupported call %r in a value set: use "
                                "vdc.rangelist(...), a list literal, range(lo, hi) "
                                "(half-open) or vdc.r[lo:hi] (inclusive)"
                                % (callee or "<expr>"))
            items = node.args
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            items = node.elts
        elif self._const_collection(node) is not None:
            return self._collection_entries(node, self._const_collection(node))
        elif self._is_array(node):
            # self.arr: the elements' values, as classic list_t.__contains__.
            return [IRRange(self._expr(node))]
        elif self._is_own_class_attr(node) or (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == self.self_name):
            # self.NAME / T.NAME: a collection held in a class attribute,
            # read on each subclass when its type is built.
            return [IRRange(IRClassConst(node.attr, self._where(node),
                                         as_set=True))]
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            # vdc.r[lo:hi]
            return [self._slice_range(node.slice)]
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Tuple):
            # vdc.r[lo:hi, lo2:hi2] -- a union of inclusive ranges
            out = []
            for e in node.slice.elts:
                if not isinstance(e, ast.Slice):
                    self._err(node, "every entry of a multi-range slice must be "
                                    "a range (r[lo:hi, lo2:hi2])")
                out.append(self._slice_range(e))
            return out
        else:
            self._err(node, "value set must be a rangelist(...), a list literal, "
                            "range(lo, hi) or vdc.r[lo:hi]")
        # Range endpoints are general expressions (constants, fields, or arithmetic
        # over them) — not just literals — so `a inside [rng(c, d)]` / `[b, b+1]`
        # with rand endpoints works like the classic front-end. A literal endpoint
        # lowers to ExprLiteralModel exactly as before (IRConst); a field endpoint
        # lowers to its field-ref model.
        out = []
        for it in items:
            if isinstance(it, ast.Tuple) and len(it.elts) == 2:
                out.append(IRRange(self._expr(it.elts[0]), self._expr(it.elts[1])))
            elif isinstance(it, ast.Call) and self._callee_name(it) == "rng":
                out.append(IRRange(self._expr(it.args[0]), self._expr(it.args[1])))
            elif isinstance(it, ast.Call) and self._callee_name(it) == "range":
                # `a in [range(3, 50), range(100, 200)]` -- a union of half-open ranges
                out.append(self._range_call(it))
            elif isinstance(it, ast.Subscript) and isinstance(it.slice, ast.Slice):
                out.append(self._slice_range(it.slice))
            elif isinstance(it, ast.List):
                for e in it.elts:
                    out.append(IRRange(self._expr(e)))
            elif isinstance(it, ast.Starred):
                coll = self._const_collection(it.value)
                if coll is None:
                    self._err(it, "only a constant collection can be unpacked "
                                  "with '*' in a value set")
                out.extend(self._collection_entries(it, coll))
            else:
                out.append(IRRange(self._expr(it)))
        return out

    def _const_collection(self, node):
        """The list, tuple, set, frozenset or range a module global, closure
        variable or ``module.NAME`` / ``Class.NAME`` path names, or None. Read
        when the class is defined, as int constants are."""
        if isinstance(node, ast.Name):
            if (node.id in self._params or node.id in self._bound
                    or node.id not in self._names):
                return None
            value = self._names[node.id]
        elif isinstance(node, ast.Attribute):
            attrs = []
            cur = node
            while isinstance(cur, ast.Attribute):
                attrs.insert(0, cur.attr)
                cur = cur.value
            if (not isinstance(cur, ast.Name) or cur.id == self.self_name
                    or cur.id == self.own_class or cur.id not in self._names):
                return None
            value = self._names[cur.id]
            for a in attrs:
                value = getattr(value, a, None)
        else:
            return None
        return value if isinstance(value, _COLLECTIONS) else None

    def _collection_entries(self, node, coll):
        if isinstance(coll, range):
            if coll.step == 1:
                return [IRRange(IRConst(coll.start), IRConst(coll.stop - 1))] \
                    if len(coll) else []
            return [_Stepped(IRConst(coll.start), IRConst(coll.stop), coll.step)]
        return [IRRange(IRConst(self._as_int(node, v))) for v in coll]

    def _membership(self, lhs, entries, negate):
        """``lhs in entries``: an IRInside for the value and range entries, ORed
        with a test for each stepped range."""
        plain = [e for e in entries if isinstance(e, IRRange)]
        stepped = [e for e in entries if isinstance(e, _Stepped)]
        if not stepped and plain:
            return IRInside(lhs, plain, negate=negate)
        terms = [IRInside(lhs, plain)] if plain else []
        terms.extend(e.test(lhs) for e in stepped)
        result = terms[0] if terms else IRConst(0)
        for t in terms[1:]:
            result = IRBin("|", result, t)
        return IRBin("==", result, IRConst(0)) if negate else result

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
            # The weight may be a constant or a (non-rand) field reference, read at
            # solve time — so it is a general expression, not a parse-time int.
            weight = self._expr(w.args[1])
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

    def _is_array(self, node):
        """``self.<array field>``"""
        return (isinstance(node, ast.Attribute) and node.attr in self._arrays
                and isinstance(node.value, ast.Name)
                and node.value.id == self.self_name)

    def _is_self_rooted(self, node):
        cur = node
        while isinstance(cur, ast.Attribute):
            cur = cur.value
        return isinstance(cur, ast.Name) and cur.id == self.self_name

    def _root_name(self, node):
        """Walk through Attribute/Subscript chains to the root expression
        (typically a Name), used to tell field accesses from external constants."""
        cur = node
        while isinstance(cur, (ast.Attribute, ast.Subscript)):
            cur = cur.value
        return cur

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
