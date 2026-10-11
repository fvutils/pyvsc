"""
``inline_parse.skip_body``: a parsed ``randomize_with`` body is not executed.
Every test runs with both mechanisms (sys.monitoring and settrace).
"""
import sys
import threading
import unittest

from vsc.dc import inline_parse


class _CM:
    """Arms the skip for the with-statement that enters it. Like the real
    randomize_with, each call returns a new context manager."""

    def randomize_with(self):
        return _CM()

    def __enter__(self):
        frame = sys._getframe(1)
        loc = inline_parse.locate(frame)
        self.token = inline_parse.skip_body(frame, loc.node.body[0].lineno)
        assert self.token is not None
        return "it-value"

    def __exit__(self, t, v, tb):
        inline_parse.release(self.token)
        return t is inline_parse.SkipBody


class _SkipCase:
    MODE = None

    def setUp(self):
        self._saved = inline_parse._SKIP_MODE
        inline_parse._SKIP_MODE = self.MODE

    def tearDown(self):
        inline_parse._SKIP_MODE = self._saved

    def test_body_is_not_run(self):
        ran = []
        cm = _CM()
        with cm.randomize_with() as it:
            ran.append(1)
            1 / 0
        after = it
        self.assertEqual(ran, [])
        self.assertEqual(after, "it-value")

    def test_loop_and_code_after(self):
        ran, after = [], []
        cm = _CM()
        for i in range(5):
            with cm.randomize_with() as it:
                ran.append(i)
            after.append(i)
        self.assertEqual(ran, [])
        self.assertEqual(after, list(range(5)))

    def test_multi_line_header_binds_it(self):
        cm = _CM()
        with cm.randomize_with(
                ) as it:
            raise AssertionError("body ran")
        self.assertEqual(it, "it-value")

    def test_generator_frame(self):
        cm = _CM()

        def gen():
            with cm.randomize_with() as it:
                raise AssertionError("body ran")
            yield it
        self.assertEqual(list(gen()), ["it-value"])

    def test_other_threads_run_the_same_code(self):
        # Two threads run one function; only the armed frame is skipped, the
        # other thread's lines (and its own withs) behave.
        cm = _CM()
        counts = {}
        go = threading.Barrier(2)

        def work(name):
            go.wait()
            n = 0
            for _ in range(200):
                with cm.randomize_with() as it:
                    raise AssertionError("body ran")
                n += 1
            counts[name] = n

        ts = [threading.Thread(target=work, args=(k,)) for k in "ab"]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(counts, {"a": 200, "b": 200})

    def test_recursion(self):
        cm = _CM()
        out = []

        def rec(n):
            if n:
                rec(n - 1)
            with cm.randomize_with() as it:
                raise AssertionError("body ran")
            out.append(n)
        rec(3)
        self.assertEqual(out, [0, 1, 2, 3])


class TestSkipMonitoring(_SkipCase, unittest.TestCase):
    MODE = "monitoring"

    def setUp(self):
        if not hasattr(sys, "monitoring"):
            self.skipTest("sys.monitoring needs Python 3.12")
        super().setUp()


class TestSkipSettrace(_SkipCase, unittest.TestCase):
    MODE = "settrace"

    def setUp(self):
        import types
        t = sys.gettrace()
        if t is not None and not isinstance(t, (types.FunctionType,
                                                types.MethodType)):
            # e.g. coverage's CTracer: skip_body declines (legacy path), as
            # test_c_tracer_is_not_trusted checks under any tracer.
            if self._testMethodName != "test_c_tracer_is_not_trusted":
                self.skipTest("a C tracer is active")
        super().setUp()

    def test_chains_and_restores_a_tracer(self):
        events = []

        def tracer(frame, event, arg):
            events.append(event)
            return tracer
        prev = sys.gettrace()
        sys.settrace(tracer)
        try:
            cm = _CM()
            with cm.randomize_with() as it:
                raise AssertionError("body ran")
            self.assertIs(sys.gettrace(), tracer)
            x = 1
        finally:
            sys.settrace(prev)
        self.assertEqual(x, 1)
        self.assertIn("line", events)

    def test_c_tracer_is_not_trusted(self):
        # A tracer that is not a Python function may ignore frame.f_trace.
        class CallableTracer:
            def __call__(self, frame, event, arg):
                return None
        prev = sys.gettrace()
        sys.settrace(CallableTracer())
        try:
            tok = inline_parse.skip_body(sys._getframe(), 10 ** 6)
        finally:
            sys.settrace(prev)
        self.assertIsNone(tok)
