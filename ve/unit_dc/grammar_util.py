"""
Harness for the vdc constraint-grammar suite (``test_constraint_grammar.py``).

A constraint body is compiled from its source (``inspect.getsource``), so a case
cannot be built with ``exec``. Each case is written to its own module file in a
per-test temporary directory and imported from there.

Every case uses the same class, ``T`` (see ``HEADER``), and the body under test
becomes its ``c_probe`` constraint. ``BODY_LINE0`` is the file line of the body's
first line, so a rejection can be checked against an exact ``file:line``.

The grammar itself is specified in ``doc/notes/vdc_constraint_python_grammar.md``.
"""
import enum
import importlib
import os
import shutil
import sys
import tempfile
import textwrap

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


class GrammarCase(DcTestCase):
    """Base class for the grammar tests: build a case from a body, then accept,
    reject or compare it."""

    def setUp(self):
        super().setUp()
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
        return HEADER + textwrap.indent(textwrap.dedent(body).strip("\n"),
                                        _INDENT) + "\n"

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
        with self.assertRaises(ConstraintParseError) as cm:
            mod = self.build(body, src=src)
            getattr(mod, cls)()     # some rejections come from the type model
        msg = str(cm.exception)
        self.assertIn(fragment, msg)
        name = self._mods[-1]
        abs_line = line if src is not None else BODY_LINE0 + line - 1
        self.assertIn("%s.py:%d)" % (name, abs_line), msg)
        return msg

    def same_model(self, body_a, body_b, cls="T"):
        """Assert both bodies lower to the same constraint model."""
        self.assertEqual(self.model_dump(body_a, cls), self.model_dump(body_b, cls))

    def model_dump(self, body, cls="T"):
        from vsc.dc import solve_view
        obj = getattr(self.build(body), cls)()
        node = solve_view.build_solve_node(obj, obj._get_type_model())
        return [dump_model(b) for b in node.composite.constraint_model_l
                if b.name == "c_probe"]


def _show(obj):
    tm = obj._get_type_model()
    return ", ".join("%s=%r" % (f.name, getattr(obj, f.name)) for f in tm.fields)


# Back-references, source info and lazily computed caches: not part of the tree.
_SKIP_ATTRS = frozenset(("parent", "srcinfo", "rand_if", "srcinfo_decl",
                         "_width_valid", "equality_ops", "relational_ops"))


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
