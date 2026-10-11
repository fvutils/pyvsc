"""
``inline_parse.locate``: finding a ``randomize_with`` body from the frame
that enters it, in the shapes user code takes.
"""
import functools
import linecache
import sys
import unittest

from vsc.dc import inline_parse


class _CM:
    """Records what ``locate`` finds for the frame that enters it."""

    def __init__(self):
        self.found = []

    def randomize_with(self):
        return self

    def __enter__(self):
        self.found.append(inline_parse.locate(sys._getframe(1)))
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return 0                    # the body runs here (nothing skips it)


def _body_src(loc):
    import ast
    return [ast.unparse(s) for s in loc.node.body]


class TestInlineLocate(unittest.TestCase):

    def setUp(self):
        self.a = _CM()
        self.b = _CM()

    def test_function(self):
        a = self.a
        with a.randomize_with() as it:
            it.x == 1
        loc = a.found[0]
        self.assertEqual(loc.it_name, "it")
        self.assertEqual(_body_src(loc), ["it.x == 1"])

    def test_loop_reuses_the_site(self):
        a = self.a
        for _ in range(3):
            with a.randomize_with() as it:
                it.x == 2
        self.assertIs(a.found[0], a.found[1])
        self.assertIs(a.found[1], a.found[2])

    def test_two_sites(self):
        a = self.a
        with a.randomize_with() as p:
            p.x == 1
        with a.randomize_with() as q:
            q.x == 2
        self.assertEqual([l.it_name for l in a.found], ["p", "q"])

    def test_method_and_closure(self):
        a = self.a

        class Holder:
            def go(self):
                with a.randomize_with() as m:
                    m.x == 3

        def outer():
            k = 4

            def inner():
                with a.randomize_with() as c:
                    c.x == k
            inner()
        Holder().go()
        outer()
        self.assertEqual([l.it_name for l in a.found], ["m", "c"])
        self.assertEqual(_body_src(a.found[1]), ["c.x == k"])

    def test_decorated(self):
        a = self.a

        def deco(f):
            @functools.wraps(f)
            def w(*args):
                return f(*args)
            return w

        @deco
        def run():
            with a.randomize_with() as d:
                d.x == 5
        run()
        self.assertEqual(_body_src(a.found[0]), ["d.x == 5"])

    def test_two_items_on_one_line(self):
        a, b = self.a, self.b
        with a.randomize_with() as x, b.randomize_with() as y:
            x.v == 1
        self.assertEqual(a.found[0].it_name, "x")
        self.assertEqual(b.found[0].it_name, "y")
        self.assertIs(a.found[0].node, b.found[0].node)

    def test_one_line_withs(self):
        a, b = self.a, self.b
        with a.randomize_with() as x: x.v == 1     # noqa: E701
        with b.randomize_with() as y: y.v == 2     # noqa: E701
        self.assertEqual(_body_src(a.found[0]), ["x.v == 1"])
        self.assertEqual(_body_src(b.found[0]), ["y.v == 2"])

    def test_multi_line_header(self):
        a = self.a
        with a.randomize_with(
                ) as it:
            it.x == 6
        self.assertEqual(_body_src(a.found[0]), ["it.x == 6"])

    def test_nested_withs(self):
        a, b = self.a, self.b
        with a.randomize_with() as outer:
            with b.randomize_with() as inner:
                inner.x == 7
        self.assertEqual(a.found[0].it_name, "outer")
        self.assertEqual(b.found[0].it_name, "inner")

    def test_no_as_name(self):
        a = self.a
        with a.randomize_with():
            pass
        self.assertIsNone(a.found[0])

    def test_linecache_entry(self):
        # IPython registers each cell in linecache under a pseudo filename.
        name = "<ipython-input-vdc-1>"
        src = ("def cell(a):\n"
               "    with a.randomize_with() as it:\n"
               "        it.x == 8\n")
        linecache.cache[name] = (len(src), None, src.splitlines(True), name)
        try:
            g = {}
            exec(compile(src, name, "exec"), g)
            g["cell"](self.a)
        finally:
            del linecache.cache[name]
        self.assertEqual(_body_src(self.a.found[0]), ["it.x == 8"])

    def test_no_source(self):
        src = ("def cell(a):\n"
               "    with a.randomize_with() as it:\n"
               "        it.x == 9\n")
        g = {}
        exec(compile(src, "<string-vdc-nosrc>", "exec"), g)
        g["cell"](self.a)
        self.assertIsNone(self.a.found[0])
