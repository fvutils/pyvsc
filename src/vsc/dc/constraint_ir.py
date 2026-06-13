"""
Constraint IR — the instance-independent intermediate representation produced by
:mod:`vsc.dc.constraint_parser` (once per type) and consumed by
:mod:`vsc.dc.ir_lower` (per randomize, binding field names to FieldScalarModels).

The IR is deliberately small and serializable-shaped: expression nodes reference
fields *by name*, never by model object, so a single parsed program is shared
immutably across all instances of a type.

See ``doc/notes/dataclass_pyvsc_impl_test_doc_plan.md`` §2.3.
"""

# --- Expression nodes -------------------------------------------------------


class IRNode:
    __slots__ = ()


class IRConst(IRNode):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "IRConst(%r)" % (self.value,)


class IRField(IRNode):
    """A reference to ``self.<name>`` (a dotted path is stored as a tuple)."""
    __slots__ = ("path",)

    def __init__(self, path):
        # path: tuple of attribute names, e.g. ("addr",) or ("sub", "x")
        self.path = tuple(path)

    @property
    def name(self):
        return self.path[0]

    def __repr__(self):
        return "IRField(%s)" % (".".join(self.path),)


class IRBin(IRNode):
    """Binary op. ``op`` is the string token ('==','<','+','&',...)."""
    __slots__ = ("op", "lhs", "rhs")

    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs

    def __repr__(self):
        return "IRBin(%r, %r, %r)" % (self.op, self.lhs, self.rhs)


class IRUnary(IRNode):
    """Unary op. ``op`` is '~' (bitwise/logical not) or '-' (negate)."""
    __slots__ = ("op", "operand")

    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

    def __repr__(self):
        return "IRUnary(%r, %r)" % (self.op, self.operand)


class IRRange(IRNode):
    """A single entry in an inside/rangelist: a point (hi is None) or [lo,hi]."""
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        self.lo = lo
        self.hi = hi


class IRInside(IRNode):
    """``<lhs> inside { ranges }``. ``negate`` for outside/not_inside."""
    __slots__ = ("lhs", "ranges", "negate")

    def __init__(self, lhs, ranges, negate=False):
        self.lhs = lhs
        self.ranges = ranges      # list[IRRange]
        self.negate = negate


class IRIndex(IRNode):
    """Array element access ``base[index]`` (base is usually an IRField)."""
    __slots__ = ("base", "index")

    def __init__(self, base, index):
        self.base = base
        self.index = index


# --- Statement nodes --------------------------------------------------------


class IRConstraintExpr(IRNode):
    """A bare boolean constraint expression statement."""
    __slots__ = ("expr",)

    def __init__(self, expr):
        self.expr = expr


class IRIfElse(IRNode):
    """if_then / else_if / else_then. ``false_body`` is a list of statements or a
    nested IRIfElse (for else_if chains), or None."""
    __slots__ = ("cond", "true_body", "false_body")

    def __init__(self, cond, true_body, false_body=None):
        self.cond = cond
        self.true_body = true_body
        self.false_body = false_body


class IRImplies(IRNode):
    __slots__ = ("cond", "body")

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body          # list of statements


class IRSoft(IRNode):
    __slots__ = ("expr",)

    def __init__(self, expr):
        self.expr = expr


class IRUnique(IRNode):
    __slots__ = ("terms",)

    def __init__(self, terms):
        self.terms = terms        # list of expression nodes


class IRSolveOrder(IRNode):
    """solve_order(before, after): each side is a list of IRField."""
    __slots__ = ("before", "after")

    def __init__(self, before, after):
        self.before = before      # list[IRField]
        self.after = after        # list[IRField]


class IRWeight(IRNode):
    """One dist weight: value point (hi None) or [lo,hi] range, weight, per_value."""
    __slots__ = ("lo", "hi", "weight", "per_value")

    def __init__(self, lo, hi, weight, per_value):
        self.lo = lo
        self.hi = hi
        self.weight = weight
        self.per_value = per_value


class IRDist(IRNode):
    __slots__ = ("lhs", "weights")

    def __init__(self, lhs, weights):
        self.lhs = lhs
        self.weights = weights    # list[IRWeight]


class IRForeach(IRNode):
    """foreach over an array. ``idx_name``/``it_name`` are the loop variables bound
    by the ``as`` target (either may be None); ``body`` is the loop body."""
    __slots__ = ("array", "idx_name", "it_name", "body")

    def __init__(self, array, idx_name, it_name, body):
        self.array = array        # IRField (path to the array)
        self.idx_name = idx_name
        self.it_name = it_name
        self.body = body          # list of statements


# --- Program ----------------------------------------------------------------


class ConstraintProgram:
    """The compiled form of one ``@vdc.constraint`` method."""
    __slots__ = ("name", "kind", "stmts")

    def __init__(self, name, stmts, kind="block"):
        self.name = name
        self.kind = kind
        self.stmts = stmts        # list of statement nodes

    def __repr__(self):
        return "ConstraintProgram(%r, %d stmts)" % (self.name, len(self.stmts))
