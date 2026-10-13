'''
Execute every runnable example under examples/dc/ so the docs never drift from the
implementation (plan §4: "every code block ... has a mirror in examples/dc/ that CI
executes"). Each example's main() asserts its own expected results.
'''
import importlib.util
import os

from dc_test_case import DcTestCase
from vsc.dc import inline

_EX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "dc"))


# Examples whose randomize_with bodies use the parsed grammar ('and', 'or',
# 'not', 'if'). The legacy operator path (VSC_DC_INLINE_PARSE=0) cannot run
# them; it rejects such a body with a TypeError by design.
_NEEDS_INLINE_PARSE = {"10_inline.py"}


def _examples():
    if not os.path.isdir(_EX_DIR):
        return []
    return sorted(f for f in os.listdir(_EX_DIR) if f.endswith(".py"))


class TestExamplesDc(DcTestCase):

    def test_examples_run(self):
        examples = _examples()
        self.assertTrue(examples, "no examples found under examples/dc/")
        for fname in examples:
            with self.subTest(example=fname):
                if fname in _NEEDS_INLINE_PARSE and not inline._INLINE_PARSE:
                    self.skipTest("needs the inline parser")
                path = os.path.join(_EX_DIR, fname)
                spec = importlib.util.spec_from_file_location(
                    "dc_example_" + fname[:-3], path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self.assertTrue(hasattr(mod, "main"),
                                "%s has no main()" % fname)
                mod.main()
