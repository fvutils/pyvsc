"""
Parsed ``randomize_with`` bodies.

``with obj.randomize_with() as it:`` bodies follow the ``@vdc.constraint``
grammar: the body is parsed from source, never executed. This module finds the
body from the caller's frame (``locate``); see
``doc/notes/vdc_constraint_python_grammar.md`` §7 for the design.

:mod:`vsc.dc.inline` keeps the operator-overloading path, used when the source
cannot be read.
"""
import ast
import copy
import dis
import enum
import linecache
import sys
import types

from .constraint_ir import ConstraintProgram, IRHost, IRHostFor, IRRange
from .constraint_parser import _MAX_UNROLL, ConstraintParseError, _Parser

# Opcodes that call __enter__ for a ``with`` item.
_WITH_OPS = frozenset(("BEFORE_WITH", "SETUP_WITH"))


class Located:
    """The ``with`` statement of one call site, and the item that is ours."""
    __slots__ = ("node", "item", "it_name", "filename", "sites", "deleg",
                 "parsed")

    def __init__(self, node, item, it_name, filename):
        self.node = node              # ast.With
        self.item = item              # ast.withitem
        self.it_name = it_name        # the ``as`` name
        self.filename = filename
        self.sites = {}               # class -> Site (see inline.RandomizeWith)
        self.deleg = None             # delegates(), once known
        # (array names, field names, structural key) -> Site before class
        # constants are folded: classes with the same fields share the parse.
        self.parsed = {}

    @property
    def body_line(self):
        """The first line of the body, or None when it shares the ``with``
        line (a line event cannot then tell header from body)."""
        line = self.node.body[0].lineno
        return None if line == self.node.lineno else line


#: (code, lasti) -> Located, or None when the site cannot be parsed.
_SITES = {}

#: filename -> (lines, tree): the parsed source of a file.
_TREES = {}


def locate(frame):
    """The ``with`` statement whose ``__enter__`` ``frame`` is executing, or
    None when its source is not available or the item has no ``as`` name.
    Cached per call site."""
    code = frame.f_code
    # Code objects compare equal across files when their bytecode does (the
    # file name is not compared), so the key names the file and line too.
    key = (code, code.co_filename, code.co_firstlineno, frame.f_lasti)
    try:
        return _SITES[key]
    except KeyError:
        pass
    loc = _locate(frame)
    _SITES[key] = loc
    return loc


def _locate(frame):
    code = frame.f_code
    tree = _tree(code.co_filename, frame.f_globals)
    if tree is None:
        return None
    line = frame.f_lineno
    # The with-items entered on this line, in execution order (source order),
    # and the with-entry instructions on it: the k-th instruction enters the
    # k-th item.
    items = [(n, it) for n in sorted(
                 (n for n in ast.walk(tree)
                  if isinstance(n, ast.With) and n.lineno == line),
                 key=lambda n: n.col_offset)
             for it in n.items]
    offsets = [off for off, ln in _with_instrs(code) if ln == line]
    if frame.f_lasti not in offsets or len(offsets) != len(items):
        return None                 # the source does not match the code
    node, item = items[offsets.index(frame.f_lasti)]
    if not isinstance(item.optional_vars, ast.Name):
        return None
    return Located(node, item, item.optional_vars.id, code.co_filename)


def _tree(filename, module_globals):
    lines = linecache.getlines(filename, module_globals)
    if not lines:
        return None
    hit = _TREES.get(filename)
    if hit is not None and hit[0] is lines:
        return hit[1]
    try:
        tree = ast.parse("".join(lines), filename)
    except SyntaxError:
        return None
    _TREES[filename] = (lines, tree)
    return tree


def _with_instrs(code):
    """``(offset, line)`` of each instruction in ``code`` that enters a
    ``with`` item."""
    out = []
    line = None
    for ins in dis.get_instructions(code):
        pos = getattr(ins, "positions", None)
        if pos is not None and pos.lineno is not None:
            line = pos.lineno
        elif ins.starts_line is not None and not isinstance(ins.starts_line, bool):
            line = ins.starts_line
        if ins.opname in _WITH_OPS:
            out.append((ins.offset, line))
    return out


# -- host expressions ---------------------------------------------------------

#: Prefix of the placeholder name that stands for host expression k.
_HOST = "__vdc_host_"

#: vdc helpers: never evaluated as Python, only their arguments may be.
_HELPERS = frozenset(("rangelist", "rng", "weight", "soft", "dist", "unique",
                      "solve_order", "if_then", "else_if", "else_then",
                      "implies", "foreach"))

# Nodes of a literal: an expression the parser reads without a name lookup.
_LITERAL_NODES = (ast.Constant, ast.UnaryOp, ast.BinOp, ast.Tuple, ast.List,
                  ast.Set, ast.expr_context, ast.operator, ast.unaryop)

_COMPREHENSIONS = (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp,
                   ast.Lambda)


def _callee(node):
    f = node.func if isinstance(node, ast.Call) else node
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _names_of(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        out = set()
        for e in target.elts:
            out |= _names_of(e)
        return out
    return set()


class _Hosts:
    """Replaces each maximal sub-expression of a body that names neither the
    ``as`` target nor a loop name by a placeholder name, and keeps the
    original: those are the host expressions, evaluated by Python per call."""

    def __init__(self):
        self.nodes = []
        self.idle = []              # statements that name no 'it'

    def stmts(self, body, bound):
        return [self.stmt(s, bound) for s in body]

    def stmt(self, s, bound):
        if isinstance(s, ast.Expr):
            if self._hostable(s.value, bound):
                self.idle.append(s)
            s.value = self.expr(s.value, bound)
        elif isinstance(s, ast.If):
            s.test = self.expr(s.test, bound)
            s.body = self.stmts(s.body, bound)
            s.orelse = self.stmts(s.orelse, bound)
        elif isinstance(s, ast.For):
            s.iter = self.expr(s.iter, bound)
            s.body = self.stmts(s.body, bound | _names_of(s.target))
            s.orelse = self.stmts(s.orelse, bound)
        elif isinstance(s, ast.With):
            inner = set(bound)
            for item in s.items:
                # The context manager (vdc.if_then, vdc.else_then, ...) is
                # the parser's to read; only its arguments may be hosts.
                ce = item.context_expr
                if isinstance(ce, ast.Call):
                    ce.args = [self.expr(a, bound) for a in ce.args]
                    for kw in ce.keywords:
                        kw.value = self.expr(kw.value, bound)
                if item.optional_vars is not None:
                    inner |= _names_of(item.optional_vars)
            s.body = self.stmts(s.body, frozenset(inner))
        elif isinstance(s, getattr(ast, "Match", ())):
            s.subject = self.expr(s.subject, bound)
            for case in s.cases:
                case.body = self.stmts(case.body, bound)
        return s

    def expr(self, e, bound):
        if self._hostable(e, bound):
            k = len(self.nodes)
            self.nodes.append(e)
            return ast.copy_location(ast.Name(id=_HOST + str(k), ctx=ast.Load()), e)
        if isinstance(e, ast.Call):
            e.args = [self.expr(a, bound) for a in e.args]
            for kw in e.keywords:
                kw.value = self.expr(kw.value, bound)
            return e
        if isinstance(e, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            inner = set(bound)
            for i, g in enumerate(e.generators):
                g.iter = self.expr(g.iter, frozenset(inner) if i else bound)
                inner |= _names_of(g.target)
                g.ifs = [self.expr(c, frozenset(inner)) for c in g.ifs]
            e.elt = self.expr(e.elt, frozenset(inner))
            return e
        if isinstance(e, ast.Subscript) and _callee(e.value) == "r":
            e.slice = self.expr(e.slice, bound)     # vdc.r[lo:hi]
            return e
        for field, value in ast.iter_fields(e):
            if isinstance(value, ast.expr):
                setattr(e, field, self.expr(value, bound))
            elif isinstance(value, list):
                setattr(e, field, [self.expr(v, bound) if isinstance(v, ast.expr)
                                   else v for v in value])
        return e

    @staticmethod
    def _hostable(e, bound):
        if not isinstance(e, ast.expr) or isinstance(e, (ast.Starred, ast.Slice)):
            return False
        nodes = list(ast.walk(e))
        if any(isinstance(n, ast.Slice) for n in nodes):
            return False                    # vdc.r[1:2, 8:9]: the parser's
        if all(isinstance(n, _LITERAL_NODES) for n in nodes):
            return False                    # a literal: the parser reads it
        for n in nodes:
            if isinstance(n, ast.Name) and n.id in bound:
                return False
            if isinstance(n, ast.Call) and _callee(n) in _HELPERS:
                return False
            if isinstance(n, ast.Subscript) and _callee(n.value) == "r":
                return False
        return True


# Builtins the grammar reads (constraint_parser._BUILTINS and the loop forms).
_GRAMMAR_CALLS = frozenset(("abs", "all", "any", "bool", "len", "max", "min",
                            "sum", "range", "enumerate", "prod"))


def delegates(body, it_name):
    """True when ``body`` passes ``it`` (or a name bound over it) to a Python
    callable: a helper function that adds constraints, which only running the
    body can do. Such a site keeps the legacy path."""
    bound = {it_name}
    for n in ast.walk(ast.Module(body=list(body), type_ignores=[])):
        if isinstance(n, (ast.For, ast.comprehension)):
            bound |= _names_of(n.target)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            bound |= _names_of(n.optional_vars)
    for n in ast.walk(ast.Module(body=list(body), type_ignores=[])):
        if not isinstance(n, ast.Call):
            continue
        name = _callee(n)
        f = n.func
        if name in _HELPERS or name in _GRAMMAR_CALLS:
            continue
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                and f.value.id in bound:
            continue                # it.inside(...), it.foo(...)
        # Only ``it`` itself (or a loop name) handed over: ``helper(it)``.
        # ``sorted(it.arr)`` passes a value, and the grammar rejects it.
        args = list(n.args) + [k.value for k in n.keywords]
        if any(isinstance(a, ast.Starred) and isinstance(a.value, ast.Name)
               and a.value.id in bound
               or isinstance(a, ast.Name) and a.id in bound for a in args):
            return True
    return False


def extract_hosts(body, it_name):
    """``(body, hosts)``: a copy of the statements ``body`` with each host
    expression replaced by a placeholder, and the host expressions in slot
    order."""
    out, nodes, _ = _extract(body, it_name)
    return out, nodes


def _extract(body, it_name):
    h = _Hosts()
    out = h.stmts(copy.deepcopy(body), frozenset((it_name,)))
    return out, h.nodes, h.idle


# -- parsing a body -----------------------------------------------------------


class _HostRef:
    """A host expression used as a collection (``in``) or an iterable
    (``for``)."""
    __slots__ = ("slot",)

    def __init__(self, slot):
        self.slot = slot


class _InlineParser(_Parser):
    """The constraint parser, reading placeholders as host expressions.

    Where the grammar needs a constant (an ``**`` exponent, part-select
    bounds, a ``range`` step, a ``match`` value), a host expression is
    evaluated when the site is parsed, and its value is fixed in the parsed
    body: a *structural* host. ``Site.fits`` checks per call that it still
    has that value; if not, the site is parsed again for the new value."""

    def __init__(self, it_name, names, filename, lines, arrays, fields,
                 hosts=()):
        _Parser.__init__(self, "randomize_with", it_name, None)
        self._names = names
        self.filename = filename
        self.lineno0 = 1                # node line numbers are the file's
        self._src_lines = [l.rstrip("\n") for l in lines]
        self._arrays = arrays
        self._fields = fields
        self._hosts = hosts
        self.kinds = {}
        self.struct = {}                # slot -> value fixed at parse time

    def _fix(self, node):
        """``node`` as a constant when it is a host placeholder: evaluated
        now, and recorded as structural. Other nodes are returned as is."""
        k = self._slot(node)
        if k is None:
            return node
        if k not in self.struct:
            h = self._hosts[k]
            code = compile(ast.fix_missing_locations(ast.Expression(
                copy.deepcopy(h))), self.filename, "eval")
            v = eval(code, self._names)
            if not isinstance(v, (int, enum.Enum)):
                self._err(node, "%r is %s, not an int, bool or enum constant"
                          % (ast.unparse(h), type(v).__name__))
            self.struct[k] = _to_int(v)
            self.kinds[k] = "value"
        return ast.copy_location(ast.Constant(self.struct[k]), node)

    def _const(self, node):
        return _Parser._const(self, self._fix(node))

    def _pow(self, node):
        node = copy.copy(node)
        node.right = self._fix(node.right)
        return _Parser._pow(self, node)

    def _range_call(self, node):
        if len(node.args) == 3:
            node = copy.copy(node)
            node.args = node.args[:2] + [self._fix(node.args[2])]
        return _Parser._range_call(self, node)

    @staticmethod
    def _slot(node):
        if isinstance(node, ast.Name) and node.id.startswith(_HOST):
            return int(node.id[len(_HOST):])
        return None

    def _expr(self, node):
        k = self._slot(node)
        if k is not None:
            if k in self.struct:
                return _Parser._expr(self, self._fix(node))
            self.kinds[k] = "value"
            return IRHost(k)
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            # Part-select bounds are checked (hi:lo order) at parse time.
            sl = copy.copy(node.slice)
            sl.lower, sl.upper = self._fix(sl.lower), self._fix(sl.upper)
            node = copy.copy(node)
            node.slice = sl
        return _Parser._expr(self, node)

    def _const_collection(self, node):
        k = self._slot(node)
        if k is not None:
            return _HostRef(k)
        return _Parser._const_collection(self, node)

    def _collection_entries(self, node, coll):
        if isinstance(coll, _HostRef):
            self.kinds[coll.slot] = "set"
            return [IRRange(IRHost(coll.slot, "set"))]
        return _Parser._collection_entries(self, node, coll)

    def _const_iterable(self, it):
        k = self._slot(it)
        if k is not None:
            return _HostRef(k)
        return _Parser._const_iterable(self, it)

    def _unroll(self, stmt, values):
        if not isinstance(values, _HostRef):
            return _Parser._unroll(self, stmt, values)
        tgt = stmt.target
        if isinstance(tgt, ast.Name):
            names = (tgt.id,)
        elif (isinstance(tgt, ast.Tuple)
                and all(isinstance(e, ast.Name) for e in tgt.elts)):
            names = tuple(e.id for e in tgt.elts)
        else:
            self._err(stmt, "a constant 'for' binds a name or a tuple of names")
        self.kinds[values.slot] = "iter"
        saved = set(self._bound)
        self._bound.update(names)
        try:
            body = self.parse_body(stmt.body)
        finally:
            self._bound = saved
        return IRHostFor(names, values.slot, body)


class Site:
    """One ``randomize_with`` call site, parsed for one class."""
    __slots__ = ("prog", "code", "kinds", "srcs", "merge_globals", "filename",
                 "folded", "body_line", "struct", "inert", "control",
                 "fold_cache")

    def __init__(self, prog, code, kinds, srcs, merge_globals, filename,
                 struct=()):
        self.prog = prog
        self.struct = struct            # ((slot, value), ...) fixed when parsed
        self.inert = False              # the body compiles to no code
        self.control = None             # host slots in conditions (inline)
        self.fold_cache = None          # their values -> folded program
        self.code = code                # evaluates the host tuple
        self.kinds = kinds              # per slot: value / set / iter
        self.srcs = srcs                # per slot: (source text, line)
        self.merge_globals = merge_globals
        self.filename = filename
        self.folded = None            # prog with the class's constants folded
        self.body_line = None

    def values(self, frame):
        """The host values for this call, checked and converted."""
        if not self.kinds:
            return ()
        if self.merge_globals:
            # A comprehension or lambda in a host expression is a nested
            # scope, which reads the caller's locals only as globals.
            g = dict(frame.f_globals)
            g.update(frame.f_locals)
            raw = eval(self.code, g)
        else:
            raw = eval(self.code, frame.f_globals, frame.f_locals)
        kinds = self.kinds
        _int = self._int
        # Most hosts are plain ints: no call for those.
        return tuple([v if type(v) is int and kinds[k] == "value"
                      else (_int(k, v) if kinds[k] == "value"
                            else self._convert(k, v))
                      for k, v in enumerate(raw)])

    def fits(self, values):
        """True when this call's ``values`` keep every structural host at the
        value it was parsed with."""
        for k, v in self.struct:
            if values[k] != v:
                return False
        return True

    def struct_key(self, values):
        return tuple(values[k] for k, _ in self.struct)

    def _convert(self, k, v):
        kind = self.kinds[k]
        if kind == "value":
            return self._int(k, v)
        if kind == "set":
            # A tuple of entries: ints, and ranges (step 1: an interval;
            # another step: tested as range membership at lowering). A
            # (lo, hi) pair inside the collection is the interval lo..hi,
            # as in a list literal (a top-level tuple is a set of values).
            if isinstance(v, range):
                return v if v.step == 1 else (v,)
            if not isinstance(v, (list, tuple, set, frozenset)):
                self._bad(k, v, "a list, tuple, set, frozenset or range")
            out = []
            for e in v:
                t = type(e)
                if t is int:
                    out.append(e)
                    continue
                m = _ENUM_MAPS.get(t)
                if m is not None:
                    out.append(m[e])
                    continue
                if isinstance(e, enum.Enum):
                    m = _ENUM_MAPS[t] = {x: _to_int(x) for x in t}
                    out.append(m[e])
                elif isinstance(e, range):
                    out.append(e)
                elif isinstance(e, tuple) and len(e) == 2:
                    lo, hi = self._int(k, e[0]), self._int(k, e[1])
                    out.append(range(lo, hi + 1))
                else:
                    out.append(self._int(k, e))
            return tuple(out)
        out = []
        for e in v:
            out.append(tuple(self._int(k, x) for x in e)
                       if isinstance(e, tuple) else self._int(k, e))
            if len(out) > _MAX_UNROLL:
                src, line = self.srcs[k]
                raise ConstraintParseError(
                    "constraint 'randomize_with' (%s:%d): a constant 'for' "
                    "unrolls to at most %d iterations ('%s')"
                    % (self.filename, line, _MAX_UNROLL, src))
        return out

    def _int(self, k, v):
        t = type(v)
        if t is int:
            return v
        m = _ENUM_MAPS.get(t)
        if m is not None:
            return m[v]
        if isinstance(v, enum.Enum):
            m = _ENUM_MAPS[t] = {x: _to_int(x) for x in t}
            return m[v]
        if isinstance(v, int):
            return int(v)                   # bool, or an int subclass
        self._bad(k, v, "an int, bool or enum")

    def _bad(self, k, v, want):
        src, line = self.srcs[k]
        raise TypeError("randomize_with (%s:%d): '%s' is %s, not %s"
                        % (self.filename, line, src, type(v).__name__, want))


#: enum class -> {member: the member's solver int} (Site._int's cache).
_ENUM_MAPS = {}


def _to_int(v):
    """A host value (an int, bool or enum member) as the solver's int."""
    if isinstance(v, enum.Enum):            # an IntEnum is an int too
        from vsc.impl.enum_info import EnumInfo
        return int(EnumInfo.get(type(v)).e2v(v))
    return int(v)                           # bool, or an int subclass


def compile_site(loc, frame, arrays, fields):
    """Parse ``loc``'s body for a class with these array and field names."""
    body, hosts, idle = _extract(loc.node.body, loc.it_name)
    names = dict(frame.f_globals)
    names.update(frame.f_locals)
    lines = linecache.getlines(loc.filename, frame.f_globals)
    p = _InlineParser(loc.it_name, names, loc.filename, lines, arrays, fields,
                      hosts)
    for s in idle:
        # Evaluating it would run Python (a call, say) for no constraint.
        p._err(s, "this statement does not mention '%s', so it constrains "
                  "nothing; a randomize_with body is parsed, not run"
                  % loc.it_name)
    prog = ConstraintProgram("randomize_with", p.parse_body(body))
    code = compile(ast.fix_missing_locations(ast.Expression(
        ast.Tuple(elts=hosts, ctx=ast.Load()))), loc.filename, "eval")
    kinds = [p.kinds.get(k, "value") for k in range(len(hosts))]
    srcs = [(ast.unparse(h), h.lineno) for h in hosts]
    merge = any(isinstance(n, _COMPREHENSIONS) for h in hosts for n in ast.walk(h))
    return Site(prog, code, kinds, srcs, merge, loc.filename,
                tuple(sorted(p.struct.items())))


# -- not executing the body ---------------------------------------------------


class SkipBody(Exception):
    """Raised at the first line of a parsed ``randomize_with`` body, so the
    body does not run; ``RandomizeWith.__exit__`` suppresses it."""


#: How a body is skipped: "monitoring" (sys.monitoring, 3.12+) or "settrace".
#: Private; tests set it to run both on one interpreter.
_SKIP_MODE = "monitoring" if hasattr(sys, "monitoring") else "settrace"

_TOOL = None            # our sys.monitoring tool id, once claimed
_NO_TOOL = -1           # every free tool id was taken
_armed = {}             # code -> {id(frame): (frame, first body line)}


def inert(body):
    """True when ``body`` compiles to no code (``pass``, ``...``, constants
    and strings only), so it runs nothing and needs no skip. Arming the hook
    for it would fire in the ``with`` statement's exit code instead."""
    return all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr)
               and isinstance(s.value, ast.Constant)) for s in body)


#: The token of a body that needs no skip (see ``inert``).
NO_SKIP = ("none",)


def skip_body(frame, body_line):
    """Arm a hook that raises SkipBody when ``frame`` reaches ``body_line`` or
    a later line. Returns a token for ``release``, or None when no hook can be
    armed (then the body must run on the legacy path)."""
    if _SKIP_MODE == "monitoring" and _tool() != _NO_TOOL:
        code = frame.f_code
        frames = _armed.get(code)
        if frames is None:
            frames = _armed[code] = {}
            sys.monitoring.set_local_events(_TOOL, code, sys.monitoring.events.LINE)
        frames[id(frame)] = (frame, body_line)
        return ("monitoring", frame)
    return _trace_arm(frame, body_line)


def release(token):
    """Disarm the hook ``skip_body`` returned ``token`` for."""
    if token is NO_SKIP:
        return
    if token[0] == "monitoring":
        frame = token[1]
        code = frame.f_code
        frames = _armed.get(code)
        if frames is not None:
            frames.pop(id(frame), None)
            if not frames:
                del _armed[code]
                sys.monitoring.set_local_events(_TOOL, code, 0)
    else:
        _, frame, prev_global, prev_local = token
        frame.f_trace = prev_local
        sys.settrace(prev_global)


def _tool():
    global _TOOL
    if _TOOL is None:
        M = sys.monitoring
        _TOOL = _NO_TOOL
        for tid in (4, 3):          # the ids CPython leaves unassigned
            if M.get_tool(tid) is None:
                M.use_tool_id(tid, "vsc.dc randomize_with")
                M.register_callback(tid, M.events.LINE, _on_line)
                _TOOL = tid
                break
    return _TOOL


def _on_line(code, line):
    frames = _armed.get(code)
    if frames is None:
        return None
    frame = sys._getframe(1)
    hit = frames.get(id(frame))
    # Another thread or a recursive call can run the same code: only the
    # armed frame is skipped. The 'with' header's own lines (storing 'as it')
    # come before the body.
    if hit is None or hit[0] is not frame or line < hit[1]:
        return None
    raise SkipBody()


def _trace_arm(frame, body_line):
    prev_global = sys.gettrace()
    if prev_global is not None and not isinstance(
            prev_global, (types.FunctionType, types.MethodType)):
        # A C tracer (coverage's CTracer) does not call frame.f_trace.
        return None
    prev_local = frame.f_trace
    chained = [prev_local]

    def tracer(fr, event, arg):
        if fr is frame and event == "line" and fr.f_lineno >= body_line:
            raise SkipBody()
        if chained[0] is not None:
            # A debugger or coverage tracer was tracing this frame.
            chained[0] = chained[0](fr, event, arg)
        return tracer

    frame.f_trace = tracer
    frame.f_trace_lines = True
    if prev_global is None:
        # f_trace runs only while a global trace function is set; this one
        # traces no other frame.
        sys.settrace(_no_trace)
    return ("settrace", frame, prev_global, prev_local)


def _no_trace(frame, event, arg):
    return None
