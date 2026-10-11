"""
``randomize_with`` host expressions: which parts of a body Python evaluates
per call (``inline_parse.extract_hosts``), and their values (``Site.values``).
"""
import ast
import enum
import sys
import textwrap
import unittest

from vsc.dc import inline_parse
from vsc.dc.constraint_ir import IRHost, IRHostFor


def hosts(src, it_name="it"):
    body = ast.parse(textwrap.dedent(src)).body
    _, nodes = inline_parse.extract_hosts(body, it_name)
    return [ast.unparse(n) for n in nodes]


class TestExtractHosts(unittest.TestCase):

    def test_literals_stay(self):
        self.assertEqual(hosts("it.a == 5"), [])
        self.assertEqual(hosts("it.a == -5 + 2 * 3"), [])
        self.assertEqual(hosts("it.a in [1, (2, 4)]"), [])

    def test_values(self):
        self.assertEqual(hosts("it.a > base + 4"), ["base + 4"])
        self.assertEqual(hosts("lo < it.a < hi"), ["lo", "hi"])
        self.assertEqual(hosts("it.e == E.A"), ["E.A"])
        self.assertEqual(hosts("it.a == self.cfg.limit()"), ["self.cfg.limit()"])
        self.assertEqual(hosts("it.a == max(p, q)"), ["max(p, q)"])
        self.assertEqual(hosts("it.a == abs(it.b - off)"), ["off"])
        self.assertEqual(hosts("it.foo(k, x=j)"), ["k", "j"])

    def test_sets(self):
        self.assertEqual(hosts("it.a in allowed"), ["allowed"])
        self.assertEqual(hosts("it.a in [*vals, it.b]"), ["vals"])
        self.assertEqual(hosts("it.a in range(lo, hi)"), ["range(lo, hi)"])

    def test_helpers_are_not_evaluated(self):
        self.assertEqual(hosts("vdc.soft(it.a == k)"), ["k"])
        self.assertEqual(hosts("it.a in vdc.r[lo:hi]"), ["lo", "hi"])
        self.assertEqual(hosts("it.a in [vdc.rng(lo, hi), 9]"), ["lo", "hi"])
        self.assertEqual(hosts("vdc.dist(it.a, [vdc.weight(1, w1)])"), ["w1"])
        self.assertEqual(hosts("""
            with vdc.if_then(it.a > m):
                it.b == n
        """), ["m", "n"])

    def test_statements(self):
        self.assertEqual(hosts("""
            if mode == 3:
                it.a == 1
        """), ["mode == 3"])
        self.assertEqual(hosts("""
            for x in it.arr:
                x != bad
        """), ["bad"])
        self.assertEqual(hosts("""
            for i in range(n):
                it.arr[i] == base + i
        """), ["range(n)", "base"])
        self.assertEqual(hosts("""
            with vdc.foreach(it.arr, idx=True) as i:
                it.arr[i] < cap
        """), ["cap"])

    def test_loop_names_are_not_hosts(self):
        self.assertEqual(hosts("all(x > lo for x in it.arr)"), ["lo"])
        self.assertEqual(hosts("""
            for i, x in enumerate(it.arr):
                x == i + off
        """), ["off"])

    def test_other_as_name(self):
        self.assertEqual(hosts("t.a == it", it_name="t"), ["it"])

    def test_original_is_not_changed(self):
        body = ast.parse("it.a > base").body
        before = ast.dump(body[0])
        inline_parse.extract_hosts(body, "it")
        self.assertEqual(ast.dump(body[0]), before)


class E(enum.IntEnum):
    A = 3
    B = 7


class _Site:
    """Parses its own randomize_with body, as a class with these fields."""

    def __init__(self, fields=("a", "b", "arr"), arrays=("arr",)):
        self.fields = frozenset(fields)
        self.arrays = frozenset(arrays)
        self.site = None
        self.vals = None

    def randomize_with(self):
        return self

    def __enter__(self):
        frame = sys._getframe(1)
        loc = inline_parse.locate(frame)
        self.site = inline_parse.compile_site(loc, frame, self.arrays, self.fields)
        self.vals = self.site.values(frame)
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return _Any()


class _Any:
    """Absorbs whatever the (not yet skipped) body does with it."""

    def __getattr__(self, name):
        return self

    def __call__(self, *a, **k):
        return self

    def __iter__(self):
        return iter(())

    def __getitem__(self, k):
        return self

    def __contains__(self, k):
        return False


for _op in ("eq", "ne", "lt", "le", "gt", "ge", "add", "sub", "mul", "and",
            "or", "radd", "rsub", "rlt", "rgt"):
    setattr(_Any, "__%s__" % _op, lambda self, *a: self)


def _walk(stmts):
    out = []

    def visit(n):
        out.append(n)
        for slot in getattr(type(n), "__slots__", ()):
            v = getattr(n, slot, None)
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if hasattr(type(x), "__slots__") and type(x).__module__.endswith(
                        "constraint_ir"):
                    visit(x)
    for s in stmts:
        visit(s)
    return out


class TestSiteValues(unittest.TestCase):

    def test_values_and_kinds(self):
        s = _Site()
        base, allowed = 4, [1, E.B, True]
        with s.randomize_with() as it:
            it.a > base + 1
            it.b in allowed
            it.a != E.A
        self.assertEqual(s.site.kinds, ["value", "set", "value"])
        self.assertEqual(s.vals, (5, (1, 7, 1), 3))
        kinds = sorted(n.kind for n in _walk(s.site.prog.stmts)
                       if isinstance(n, IRHost))
        self.assertEqual(kinds, ["set", "value", "value"])

    def test_values_are_per_call(self):
        s = _Site()
        seen = []
        for base in (1, 2, 3):
            with s.randomize_with() as it:
                it.a == base * 10
            seen.append(s.vals)
        self.assertEqual(seen, [(10,), (20,), (30,)])

    def test_range_set_and_host_for(self):
        s = _Site()
        n, lo = 3, 2
        with s.randomize_with() as it:
            it.a in range(lo, lo + 4)
            for i in range(n):
                it.arr[i] == i
        self.assertEqual(s.vals[0], range(2, 6))
        self.assertEqual(s.vals[1], [0, 1, 2])
        self.assertTrue(any(isinstance(x, IRHostFor)
                            for x in _walk(s.site.prog.stmts)))

    def test_comprehension_reads_locals(self):
        s = _Site()
        vals = [1, 2]
        with s.randomize_with() as it:
            it.a in [v * 2 for v in vals]
        self.assertEqual(s.vals, ((2, 4),))

    def test_bad_value(self):
        s = _Site()
        name = "x"
        with self.assertRaisesRegex(TypeError, r"randomize_with \(.*:\d+\): "
                                    r"'name' is str, not an int, bool or enum"):
            with s.randomize_with() as it:
                it.a == name

    def test_grammar_applies(self):
        from vsc.dc.constraint_parser import ConstraintParseError
        s = _Site()
        with self.assertRaisesRegex(ConstraintParseError, "use '//'"):
            with s.randomize_with() as it:
                it.a / 2 == 1
