"""
Class-level constants in constraints.

A constraint may read a class attribute that is not a field. For example,
per-opcode subclasses can each fix ``instr_name = Op.SLLI`` on the class,
while the shared base class's constraints guard on
``self.instr_name.inside(...)``. Such a read is a constant of the subclass,
not solver state.

When a type model is built, :func:`fold_program` replaces each of these
reads with its value, then folds the if/else, implies and expression
statements that the replacement decides. Each subclass therefore gets its
own programs, with a guard either removed or its body kept
unconditionally, and the guard costs nothing per randomize.

Only plain int, bool and Enum class attributes qualify. Fields, methods,
properties, dotted paths and foreach loop variables are left alone, so an
unknown name still fails at lowering as before.
"""
import enum

from . import constraint_ir as ir

_MISSING = object()


def lookup_for(cls, field_names):
    """Return ``name -> int or None``: the solver value of class attribute
    ``name`` of ``cls`` when it is a constant (see the module doc). A bool
    stays a bool, so ``~`` can treat it as one bit. ``lookup.collection(name)``
    is the tuple of values of a list, tuple, set, frozenset or range class
    attribute, or None."""
    cache = {}

    def attr(name):
        if name in field_names or name.startswith("__"):
            return _MISSING
        return getattr(cls, name, _MISSING)

    def lookup(name):
        if name in cache:
            return cache[name]
        val = _value(attr(name))
        cache[name] = val
        return val

    def collection(name):
        v = attr(name)
        if not isinstance(v, (list, tuple, set, frozenset, range)):
            return None
        vals = tuple(_value(e) for e in v)
        return None if any(x is None for x in vals) else vals

    lookup.collection = collection
    return lookup


def _value(v):
    """The solver value of a constant, or None."""
    if isinstance(v, enum.Enum):
        from vsc.impl.enum_info import EnumInfo
        return EnumInfo.get(type(v)).e2v(v)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return int(v)
    return None


def fold_program(prog, lookup):
    """Return ``prog`` with class constants replaced and folded, or ``prog``
    itself when it reads none."""
    f = _Folder(lookup, prog.name)
    if prog.kind == "value":
        ret = f.expr(prog.ret, frozenset(prog.params))
        stmts = prog.stmts
    else:
        ret = prog.ret
        stmts = f.stmts(prog.stmts, frozenset(prog.params))
    if not f.hit:
        return prog
    return ir.ConstraintProgram(prog.name, stmts, kind=prog.kind,
                                params=prog.params, ret=ret,
                                param_defaults=prog.param_defaults)


def host_control_slots(prog):
    """The host value slots that appear in a condition (``if``, implication,
    ``x if c else y``): their values decide which statements and selects the
    body lowers to. The other host values are only literals."""
    slots = set()

    def walk(n, in_cond):
        if isinstance(n, list):
            for e in n:
                walk(e, in_cond)
            return
        if not isinstance(n, ir.IRNode):
            return
        if isinstance(n, ir.IRHost):
            if in_cond and n.kind == "value":
                slots.add(n.slot)
            return
        for name in type(n).__slots__:
            v = getattr(n, name, None)
            walk(v, in_cond or (name == "cond" and isinstance(
                n, (ir.IRIfElse, ir.IRImplies, ir.IRCond))))
    walk(prog.stmts, False)
    return tuple(sorted(slots))


def fold_host_values(prog, values, only=None):
    """``prog`` (a parsed ``randomize_with`` body) with each host value
    (``IRHost`` of kind "value") replaced by its value for this call, and the
    if/else, implies and comparisons that decides folded. Host sets and
    iterables are left for lowering. With ``only`` (a set of slots), only
    those host values are replaced; lowering reads the others."""
    f = _HostFolder(values, prog.name, only)
    stmts = f.stmts(prog.stmts, frozenset())
    if not f.hit:
        return prog
    return ir.ConstraintProgram(prog.name, stmts, kind=prog.kind,
                                params=prog.params, ret=prog.ret,
                                param_defaults=prog.param_defaults)


# Folded only when both operands are constants. Comparisons give 0/1, as the
# solver does. Arithmetic is folded only where 32-bit signed literals and
# Python ints agree (see _Folder._bin).
_CMP = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
}
_ARITH = {
    "+": lambda a, b: a + b, "-": lambda a, b: a - b,
    "*": lambda a, b: a * b, "&": lambda a, b: a & b,
    "|": lambda a, b: a | b, "^": lambda a, b: a ^ b,
}
_I32 = range(-(1 << 31), 1 << 31)


class _Folder:
    def __init__(self, lookup, cname):
        self.lookup = lookup
        self.cname = cname
        self.hit = False

    def _err(self, n, what):
        from .constraint_parser import ConstraintParseError
        raise ConstraintParseError("constraint %r %s: %r is not %s" % (
            self.cname, n.where, n.name, what))

    # -- expressions ---------------------------------------------------------

    def expr(self, n, bound):
        if isinstance(n, ir.IRField):
            if len(n.path) == 1 and n.path[0] not in bound:
                v = self.lookup(n.path[0])
                if v is not None:
                    self.hit = True
                    return ir.IRConst(int(v))
            return n
        if isinstance(n, ir.IRClassConst):
            v = self.lookup(n.name)
            if v is None:
                self._err(n, "an int, bool or enum class attribute")
            self.hit = True
            return ir.IRConst(int(v))
        if isinstance(n, ir.IRBin):
            return self._bin(n.op, self.expr(n.lhs, bound), self.expr(n.rhs, bound))
        if isinstance(n, ir.IRUnary):
            o = self.expr(n.operand, bound)
            if n.op == "~" and isinstance(o, ir.IRConst):
                # '~' is a bitwise invert at the operand's width. A boolean
                # (a comparison, a bool constant) is one bit wide, so it is
                # logical not. Otherwise the folded constant becomes a signed
                # 32-bit literal, and ~v is that literal's invert.
                if self._is_bool(n.operand, bound):
                    return ir.IRConst(int(not o.value))
                if o.value in _I32:
                    return ir.IRConst(~o.value)
            return ir.IRUnary(n.op, o)
        if isinstance(n, ir.IRCond):
            c = self.expr(n.cond, bound)
            if isinstance(c, ir.IRConst):
                return self.expr(n.t if c.value else n.f, bound)
            return ir.IRCond(c, self.expr(n.t, bound), self.expr(n.f, bound))
        if isinstance(n, ir.IRReduce):
            inner = bound | {v for v in (n.idx_name, n.it_name) if v is not None}
            return ir.IRReduce(n.op, n.array, n.idx_name, n.it_name,
                               self.expr(n.cond, inner),
                               None if n.filt is None else self.expr(n.filt, inner))
        if isinstance(n, ir.IRInside):
            lhs = self.expr(n.lhs, bound)
            ranges = []
            for r in n.ranges:
                if isinstance(r.lo, ir.IRClassConst) and r.lo.as_set:
                    vals = self.lookup.collection(r.lo.name)
                    if vals is None:
                        self._err(r.lo, "an array field or a class attribute "
                                        "holding int, bool or enum values")
                    self.hit = True
                    ranges.extend(ir.IRRange(ir.IRConst(int(v))) for v in vals)
                    continue
                ranges.append(ir.IRRange(
                    self.expr(r.lo, bound),
                    None if r.hi is None else self.expr(r.hi, bound)))
            if not ranges:
                return ir.IRConst(int(bool(n.negate)))
            if isinstance(lhs, ir.IRConst) and all(
                    isinstance(r.lo, ir.IRConst)
                    and (r.hi is None or isinstance(r.hi, ir.IRConst))
                    for r in ranges):
                v = lhs.value
                hit = any(v == r.lo.value if r.hi is None
                          else r.lo.value <= v <= r.hi.value for r in ranges)
                return ir.IRConst(int(hit != bool(n.negate)))
            return ir.IRInside(lhs, ranges, n.negate)
        if isinstance(n, ir.IRIndex):
            return ir.IRIndex(self.expr(n.base, bound), self.expr(n.index, bound))
        if isinstance(n, ir.IRPartSelect):
            return ir.IRPartSelect(self.expr(n.base, bound),
                                   self.expr(n.upper, bound),
                                   self.expr(n.lower, bound))
        if isinstance(n, ir.IRAttr):
            return ir.IRAttr(self.expr(n.base, bound), n.name)
        if isinstance(n, ir.IRConstraintRef):
            return self._ref(n, bound)
        return n

    def _is_bool(self, n, bound):
        """True when ``n`` (before folding) is one bit wide."""
        if isinstance(n, ir.IRField):
            return (len(n.path) == 1 and n.path[0] not in bound
                    and isinstance(self.lookup(n.path[0]), bool))
        if isinstance(n, ir.IRInside):
            return True
        if isinstance(n, ir.IRBin):
            if n.op in _CMP:
                return True
            if n.op in ("&", "|", "^"):
                return self._is_bool(n.lhs, bound) and self._is_bool(n.rhs, bound)
            return False
        if isinstance(n, ir.IRUnary) and n.op == "~":
            return self._is_bool(n.operand, bound)
        if isinstance(n, ir.IRClassConst):
            return isinstance(self.lookup(n.name), bool)
        return False

    def _bin(self, op, lhs, rhs):
        if isinstance(lhs, ir.IRConst) and isinstance(rhs, ir.IRConst):
            a, b = lhs.value, rhs.value
            if op in _CMP:
                return ir.IRConst(int(_CMP[op](a, b)))
            if op in _ARITH and a in _I32 and b in _I32:
                v = _ARITH[op](a, b)
                if v in _I32:
                    return ir.IRConst(v)
        return ir.IRBin(op, lhs, rhs)

    def _ref(self, n, bound):
        return ir.IRConstraintRef(
            n.name, [self.expr(a, bound) for a in n.args], n.lineno,
            {k: self.expr(v, bound) for k, v in n.kwargs.items()})

    # -- statements ----------------------------------------------------------

    def stmts(self, stmts, bound):
        out = []
        for s in stmts:
            self._stmt(s, bound, out)
        return out

    def _stmt(self, s, bound, out):
        if isinstance(s, ir.IRConstraintExpr):
            e = self.expr(s.expr, bound)
            if isinstance(e, ir.IRConst) and e.value:
                return              # always true: nothing to solve
            out.append(ir.IRConstraintExpr(e))
        elif isinstance(s, ir.IRIfElse):
            c = self.expr(s.cond, bound)
            if isinstance(c, ir.IRConst):
                taken = s.true_body if c.value else s.false_body
                if taken is not None:
                    out.extend(self.stmts(taken, bound))
                return
            fb = None if s.false_body is None else self.stmts(s.false_body, bound)
            out.append(ir.IRIfElse(c, self.stmts(s.true_body, bound), fb))
        elif isinstance(s, ir.IRImplies):
            c = self.expr(s.cond, bound)
            if isinstance(c, ir.IRConst):
                if c.value:
                    out.extend(self.stmts(s.body, bound))
                return
            out.append(ir.IRImplies(c, self.stmts(s.body, bound)))
        elif isinstance(s, ir.IRSoft):
            out.append(ir.IRSoft(self.expr(s.expr, bound)))
        elif isinstance(s, ir.IRUnique):
            out.append(ir.IRUnique([self.expr(t, bound) for t in s.terms]))
        elif isinstance(s, ir.IRDist):
            out.append(ir.IRDist(
                self.expr(s.lhs, bound),
                [ir.IRWeight(w.lo, w.hi, self.expr(w.weight, bound), w.per_value)
                 for w in s.weights]))
        elif isinstance(s, ir.IRForeach):
            inner = bound | {n for n in (s.idx_name, s.it_name) if n is not None}
            out.append(ir.IRForeach(s.array, s.idx_name, s.it_name,
                                    self.stmts(s.body, inner)))
        elif isinstance(s, ir.IRHostFor):
            out.append(ir.IRHostFor(s.names, s.slot,
                                    self.stmts(s.body, bound | set(s.names))))
        elif isinstance(s, ir.IRConstraintRef):
            out.append(self._ref(s, bound))
        else:
            out.append(s)           # IRSolveOrder: field references only


class _HostFolder(_Folder):
    """Folds a parsed ``randomize_with`` body's host values."""

    def __init__(self, values, cname, only=None):
        _Folder.__init__(self, _no_constant, cname)
        self.values = values
        self.only = only

    def expr(self, n, bound):
        if isinstance(n, ir.IRHost) and n.kind == "value" and (
                self.only is None or n.slot in self.only):
            self.hit = True
            return ir.IRConst(self.values[n.slot])
        return _Folder.expr(self, n, bound)


def _no_constant(name):
    return None


_no_constant.collection = _no_constant
