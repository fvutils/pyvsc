"""
Harness for the vdc constraint-grammar suite (``test_constraint_grammar.py``).

A constraint body is compiled from its source (``inspect.getsource``), so a case
cannot be built with ``exec``. Each case is written to its own module file in a
per-test temporary directory and imported from there.

Every case uses the same class, ``T`` (see ``HEADER``), and the body under test
becomes its ``c_probe`` constraint. ``BODY_LINE0`` is the file line of the body's
first line, so a rejection can be checked against an exact ``file:line``.

With ``INLINE = True`` (``InlineGrammarCase``) the same body is instead the body
of a parsed ``randomize_with`` block, with ``self`` renamed to the block's ``as``
name, and ``c_probe`` is empty. So every grammar test also runs inline, on the
parsed path (a fall-back to the legacy path fails the test). A case built from
``src=`` (a whole module) is not converted; it runs as a class constraint.

The grammar itself is specified in ``doc/notes/vdc_constraint_python_grammar.md``.
"""
import enum
import importlib
import os
import re
import shutil
import sys
import io
import tempfile
import textwrap
import tokenize

from dc_test_case import DcTestCase
from vsc.dc.constraint_parser import ConstraintParseError
from vsc.model.field_model import FieldModel
from vsc.model.solve_failure import SolveFailure


HEADER = '''\
import enum
import math
import vsc.dc as vdc


class E(enum.IntEnum):
    A = 1
    B = 2
    C = 3


LIMIT = 10
ALLOWED = [1, 3, 5]
ALLOWED_SET = {1, 3, 5}
ALLOWED_RANGE = range(1, 4)


def helper(x):
    return x


@vdc.dataclass
class Sub(vdc.RandClass):
    x: vdc.u8 = vdc.rand()


@vdc.dataclass
class T(vdc.RandClass):
    MAXV = 20
    MASK = 0xF0
    ON = True
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()
    c: vdc.u8 = vdc.rand()
    s: vdc.s8 = vdc.rand()
    flag: vdc.u1 = vdc.rand()
    i: vdc.u8 = vdc.rand(domain=(0, 3))
    e: E = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(size=4)
    objs: list[Sub] = vdc.rand(size=2)
    sub: Sub = vdc.rand()

    @vdc.constraint
    def c_probe(self):
'''

BODY_LINE0 = HEADER.count("\n") + 1
_INDENT = " " * 8

#: The ``as`` name of the inline block; ``self`` in a body is renamed to it.
INLINE_NAME = "me"

INLINE_HEADER = HEADER + _INDENT + "pass\n" + """

def run(obj):
    with obj.randomize_with() as %s:
""" % INLINE_NAME

INLINE_BODY_LINE0 = INLINE_HEADER.count("\n") + 1


def rename_self(body, name=INLINE_NAME):
    """``body`` with every ``self`` name token replaced by ``name``; layout,
    strings and comments are kept, so line numbers do not change."""
    toks = list(tokenize.generate_tokens(io.StringIO(body).readline))
    lines = body.splitlines(keepends=True)
    for t in reversed(toks):
        if t.type == tokenize.NAME and t.string == "self":
            (r, c), (_, c2) = t.start, t.end
            ln = lines[r - 1]
            lines[r - 1] = ln[:c] + name + ln[c2:]
        elif t.type == tokenize.STRING and t.start[0] == t.end[0] \
                and "f" in t.string[:t.string.find(t.string[-1])].lower():
            # Before 3.12 an f-string is one STRING token; 3.12 tokenizes
            # its {fields}, so their names are renamed above.
            (r, c), (_, c2) = t.start, t.end
            ln = lines[r - 1]
            lines[r - 1] = ln[:c] + _rename_in_fields(t.string, name) + ln[c2:]
    return "".join(lines)


def _rename_in_fields(fstr, name):
    """``self`` renamed inside the {fields} of the f-string ``fstr``."""
    out, depth, i = [], 0, 0
    while i < len(fstr):
        ch = fstr[i]
        if depth == 0 and fstr.startswith(("{{", "}}"), i):
            out.append(fstr[i:i + 2])
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth and re.match(r"\bself\b", fstr[i:]) \
                and not (fstr[i - 1].isalnum() or fstr[i - 1] == "_"):
            out.append(name)
            i += 4
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class GrammarCase(DcTestCase):
    """Base class for the grammar tests: build a case from a body, then accept,
    reject or compare it."""

    INLINE = False

    #: Inline mode: body -> (exception type, message fragment) for a body
    #: whose error differs inline, e.g. a host expression that Python
    #: evaluates and that raises Python's own error; None for a body that is
    #: not an error inline; "n/a" for one that cannot be an inline body.
    INLINE_DIFF = {}

    def setUp(self):
        super().setUp()
        if self.INLINE:
            self._inline_setup()
        self._dir = tempfile.mkdtemp(prefix="vdc_grammar_")
        sys.path.insert(0, self._dir)
        self._mods = []
        self._n = 0

    def tearDown(self):
        for m in self._mods:
            sys.modules.pop(m, None)
        try:
            sys.path.remove(self._dir)
        except ValueError:
            pass
        shutil.rmtree(self._dir, ignore_errors=True)
        super().tearDown()

    # -- building ------------------------------------------------------------

    def source(self, body):
        body = textwrap.dedent(body).strip("\n")
        if self.INLINE:
            return INLINE_HEADER + textwrap.indent(rename_self(body),
                                                   _INDENT) + "\n"
        return HEADER + textwrap.indent(body, _INDENT) + "\n"

    def body_line0(self):
        return INLINE_BODY_LINE0 if self.INLINE else BODY_LINE0

    def build(self, body=None, *, src=None):
        """Write a case module and import it. ``body`` goes into ``T.c_probe``;
        ``src`` is a complete module instead (for closures, inheritance, ...)."""
        self._n += 1
        name = "g_%s_%d" % (self._testMethodName, self._n)
        path = os.path.join(self._dir, name + ".py")
        with open(path, "w") as f:
            f.write(self.source(body) if src is None else textwrap.dedent(src))
        importlib.invalidate_caches()
        self._mods.append(name)
        return importlib.import_module(name)

    # -- assertions ----------------------------------------------------------

    def accept(self, body, check=None, *, n=20, unsat=False, witness=None,
               src=None, cls="T"):
        """Assert ``body`` is accepted and that every one of ``n`` randomizations
        satisfies ``check(obj)``.

        ``unsat=True`` asserts the problem has no solution instead.
        ``witness(it)`` adds inline constraints that pin a value the constraint
        must allow -- one that a narrower, wrong meaning would exclude -- and
        asserts the pinned problem still solves (non-vacuity)."""
        mod = self.build(body, src=src)
        obj = getattr(mod, cls)()
        if self.INLINE and src is None:
            return self._accept_inline(mod.run, obj, check, n, unsat, witness)
        if unsat:
            with self.assertRaises(SolveFailure):
                obj.randomize()
            return obj
        for k in range(n):
            obj.randomize()
            if check is not None:
                self.assertTrue(check(obj), "sample %d violates: %s" % (
                    k, _show(obj)))
        if witness is not None:
            with obj.randomize_with() as it:
                witness(it)
            if check is not None:
                self.assertTrue(check(obj), "witness violates: %s" % _show(obj))
        return obj

    def reject(self, body, fragment, *, line=1, src=None, cls="T"):
        """Assert ``body`` is rejected when the class is defined (before any
        ``randomize()``), with a message containing ``fragment`` and naming
        ``<file>:<line>``. ``line`` is 1-based within ``body`` (or within ``src``
        when given)."""
        exc = ConstraintParseError
        key = textwrap.dedent(body or "").strip()
        if self.INLINE and src is None and key in self.INLINE_DIFF:
            diff = self.INLINE_DIFF[key]
            if diff == "n/a":
                return None         # cannot be a randomize_with body
            if diff is None:
                # Not an error inline (see INLINE_DIFF): it must run.
                mod = self.build(body)
                self._run_parsed(mod.run, getattr(mod, cls)())
                return None
            # Inline, the body's error is a different one.
            exc, fragment = diff
        # Not assertRaises: it drops the traceback, which is checked below.
        try:
            mod = self.build(body, src=src)
            obj = getattr(mod, cls)()  # some rejections come from the type model
            if self.INLINE and src is None:
                mod.run(obj)        # raised from __enter__: the body never runs
        except exc as e:
            err = e
        else:
            self.fail("%s not raised" % exc.__name__)
        msg = str(err)
        if self.INLINE and src is None:
            fragment = re.sub(r"\bself\b", INLINE_NAME, fragment)
        self.assertIn(fragment, msg)
        name = self._mods[-1]
        abs_line = line if src is not None else self.body_line0() + line - 1
        where = "%s.py:%d)" % (name, abs_line)
        if where not in msg:
            # Python's own error (a host expression, inline): the traceback
            # names the line.
            import traceback
            tb = traceback.extract_tb(err.__traceback__)
            self.assertTrue(any(f.filename.endswith(name + ".py")
                                and f.lineno == abs_line for f in tb),
                            "%r names neither %s nor its traceback" % (msg, where))
        return msg

    def same_model(self, body_a, body_b, cls="T"):
        """Assert both bodies lower to the same constraint model."""
        self.assertEqual(self.model_dump(body_a, cls), self.model_dump(body_b, cls))

    def model_dump(self, body, cls="T"):
        from vsc.dc import solve_view
        mod = self.build(body)
        obj = getattr(mod, cls)()
        if self.INLINE:
            blocks = []
            with self._extra_blocks(None, blocks):
                self._run_parsed(mod.run, obj)
            return [dump_model(blocks[0])]
        node = solve_view.build_solve_node(obj, obj._get_type_model())
        return [dump_model(b) for b in node.composite.constraint_model_l
                if b.name == "c_probe"]

    # -- inline mode -----------------------------------------------------------

    def _inline_setup(self):
        from vsc.dc import inline
        saved_parse, saved_site = inline._INLINE_PARSE, inline._parsed_site
        self._parsed = [0]

        def counting_site(frame, obj, tm):
            site = saved_site(frame, obj, tm)
            if site is not None:
                self._parsed[0] += 1
            return site

        inline._INLINE_PARSE = True
        inline._parsed_site = counting_site

        def restore():
            inline._INLINE_PARSE = saved_parse
            inline._parsed_site = saved_site
        self.addCleanup(restore)

    def _run_parsed(self, run, obj):
        """``run(obj)``, asserting the body took the parsed path."""
        before = self._parsed[0]
        try:
            run(obj)
        finally:
            self.assertEqual(self._parsed[0], before + 1,
                             "randomize_with fell back to the legacy path")

    def _accept_inline(self, run, obj, check, n, unsat, witness):
        if unsat:
            with self.assertRaises(SolveFailure):
                self._run_parsed(run, obj)
            return obj
        for k in range(n):
            self._run_parsed(run, obj)
            if check is not None:
                self.assertTrue(check(obj), "sample %d violates: %s" % (
                    k, _show(obj)))
        if witness is not None:
            with self._extra_blocks(_witness_block(obj, witness), None):
                self._run_parsed(run, obj)
            if check is not None:
                self.assertTrue(check(obj), "witness violates: %s" % _show(obj))
        return obj

    def _extra_blocks(self, add, record):
        """A context in which each inline solve also gets block ``add`` (when
        not None), and appends its inline block to ``record`` (when not None)."""
        import contextlib
        from vsc.dc import cyclic

        @contextlib.contextmanager
        def ctx():
            orig = cyclic.do_randomize_cyclic

            def wrapped(*args, extra_blocks=None, **kw):
                if record is not None:
                    record.append(extra_blocks[0])
                if add is not None:
                    extra_blocks = list(extra_blocks) + [add]
                return orig(*args, extra_blocks=extra_blocks, **kw)
            cyclic.do_randomize_cyclic = wrapped
            try:
                yield
            finally:
                cyclic.do_randomize_cyclic = orig
        return ctx()


class InlineGrammarCase(GrammarCase):
    INLINE = True


def _witness_block(obj, witness):
    """The constraints ``witness(it)`` builds, as a block (legacy path)."""
    from vsc.dc import inline, solve_view
    from vsc.impl.ctor import pop_constraint_scope, push_constraint_scope
    from vsc.impl.expr_mode import enter_expr_mode, leave_expr_mode
    from vsc.model.constraint_block_model import ConstraintBlockModel
    _, fms = solve_view.get_solve_model(obj, obj._get_type_model())
    enter_expr_mode()
    push_constraint_scope(ConstraintBlockModel("witness"))
    try:
        witness(inline._InlineProxy(obj, fms))
    finally:
        block = pop_constraint_scope()
        leave_expr_mode()
    return block


def _show(obj):
    tm = obj._get_type_model()
    return ", ".join("%s=%r" % (f.name, getattr(obj, f.name)) for f in tm.fields)


# Back-references, source info and lazily computed caches: not part of the tree.
_SKIP_ATTRS = frozenset(("parent", "srcinfo", "rand_if", "srcinfo_decl",
                         "_width_valid", "equality_ops", "relational_ops",
                         "_vsc_reusable", "_vsc_rebind_from"))


def dump_model(m):
    """A canonical, comparable dump of a constraint/expression model tree. Field
    models are shown by name only (they are shared, not part of the tree)."""
    if isinstance(m, FieldModel):
        return ("field", getattr(m, "name", None))
    if isinstance(m, (list, tuple)):
        return tuple(dump_model(e) for e in m)
    if isinstance(m, (int, str, bool, type(None))):
        return m
    if isinstance(m, enum.Enum):
        return str(m)
    d = getattr(m, "__dict__", None)
    if d is None:
        return type(m).__name__
    return (type(m).__name__,) + tuple(
        (k, dump_model(v)) for k, v in sorted(d.items())
        if k not in _SKIP_ATTRS)
