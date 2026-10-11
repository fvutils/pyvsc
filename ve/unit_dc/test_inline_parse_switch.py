"""
``randomize_with`` with its body parsed (``VSC_DC_INLINE_PARSE=1``): the
inline suites run again with the switch on, plus what only the parsed path
does. The switch is off by default (plan 3.4).
"""
import test_inline_reuse as _reuse
import test_randomize_with as _rw
from dc_test_case import DcTestCase

import vsc.dc as vdc
from vsc.dc import inline, solve_view
from vsc.dc.constraint_parser import ConstraintParseError


class _ParseOn:
    """Runs a TestCase with randomize_with bodies parsed."""

    def setUp(self):
        self._saved_parse = inline._INLINE_PARSE
        inline._INLINE_PARSE = True
        super().setUp()

    def tearDown(self):
        super().tearDown()
        inline._INLINE_PARSE = self._saved_parse


class TestRandomizeWithParsed(_ParseOn, _rw.TestRandomizeWith):
    pass


class TestInlineReuseParsed(_ParseOn, _reuse.TestInlineReuse):
    pass


class TestInlineRebindParsed(_ParseOn, _reuse.TestInlineRebind):
    pass


@vdc.dataclass
class P(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(size=4)
    MAXV = 20


def _add_seven(it):
    it.a == 7


class TestParsedInline(_ParseOn, DcTestCase):

    def test_and_means_and(self):
        # Executed, 'x and y' is just y (an expr is truthy): a < 6 alone.
        p = P()
        for _ in range(20):
            with p.randomize_with() as it:
                it.a > 3 and it.a < 6
            self.assertTrue(3 < p.a < 6, p.a)

    def test_statement_without_it(self):
        # It would only run Python for its effect: rejected, not evaluated.
        p = P()
        ran = []
        with self.assertRaisesRegex(ConstraintParseError,
                                    "does not mention 'it', so it constrains "
                                    "nothing"):
            with p.randomize_with() as it:
                ran.append(1)
                it.a == 9
        self.assertEqual(ran, [])

    def test_host_values_per_call(self):
        p = P()
        for base in (3, 40, 77):
            with p.randomize_with() as it:
                it.a == base + 1
                for i in range(len(p.arr)):
                    it.arr[i] == base + i
            self.assertEqual(p.a, base + 1)
            self.assertEqual(list(p.arr), [base, base + 1, base + 2, base + 3])

    def test_class_constant_via_it(self):
        p = P()
        with p.randomize_with() as it:
            it.a == it.MAXV
        self.assertEqual(p.a, 20)

    def test_same_values_reuse_the_block(self):
        p = P()
        composite = solve_view.get_solve_model(p, p._get_type_model())[0]
        before = set(getattr(composite, inline._PARSED_ATTR, {}))
        blocks = []
        for k in (5, 5, 6, 6):
            with p.randomize_with() as it:
                it.a == k
            cache = getattr(composite, inline._PARSED_ATTR)
            site, = set(cache) - before
            blocks.append(cache[site][1])
            self.assertEqual(p.a, k)
        self.assertIs(blocks[0], blocks[1])
        self.assertIsNot(blocks[1], blocks[2])
        self.assertIs(blocks[2], blocks[3])

    def test_helper_function_keeps_the_legacy_path(self):
        # A body that hands 'it' to a function only works by running it.
        p = P()
        with p.randomize_with() as it:
            _add_seven(it)
        self.assertEqual(p.a, 7)

    def test_grammar_error_from_enter(self):
        p = P()
        with self.assertRaisesRegex(ConstraintParseError, "use '//'"):
            with p.randomize_with() as it:
                it.a / 2 == 1


class TestInlineSiteKey(DcTestCase):
    """Two files whose randomize_with code is byte-for-byte the same (their
    bodies differ only in constants the compiler drops) are two sites: code
    objects compare equal across files."""

    def test_equal_code_in_two_files(self):
        import importlib.util
        import os
        import tempfile
        src = ("def run(obj):\n"
               "    with obj.randomize_with() as it:\n"
               "        %s\n")
        mods = []
        with tempfile.TemporaryDirectory() as d:
            for i, body in enumerate(("1", "0")):
                path = os.path.join(d, "site_key_%d.py" % i)
                with open(path, "w") as f:
                    f.write(src % body)
                spec = importlib.util.spec_from_file_location(
                    "site_key_%d" % i, path)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                mods.append(m)
            self.assertEqual(mods[0].run.__code__, mods[1].run.__code__)
            saved = inline._INLINE_PARSE
            inline._INLINE_PARSE = True
            try:
                # Each error names its own file and constant.
                for i, m in enumerate(mods):
                    with self.assertRaisesRegex(
                            ConstraintParseError,
                            r"site_key_%d\.py:3\): a bare constant %d " % (i, 1 - i)):
                        m.run(P())
            finally:
                inline._INLINE_PARSE = saved
