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

    def test_structural_host_reparses_per_value(self):
        # An '**' exponent and part-select bounds must be constants: a host
        # there is fixed when the body is parsed, and a new value parses the
        # body again (plan 3.5).
        p = P()
        for k in (2, 3, 2):
            with p.randomize_with() as it:
                it.a ** k == 8 ** k // 8 ** (k - 1) * 0 + 2 ** k
            self.assertEqual(p.a, 2)
        for hi in (7, 3):
            with p.randomize_with() as it:
                it.a[hi:0] == 5
            self.assertEqual(p.a & ((1 << (hi + 1)) - 1), 5)

    def test_host_for_unroll_cap(self):
        p = P()
        for n in (4, 2000):
            if n > 1024:
                with self.assertRaisesRegex(ConstraintParseError,
                                            "at most 1024 iterations"):
                    with p.randomize_with() as it:
                        for i in range(n):
                            it.a != i
            else:
                with p.randomize_with() as it:
                    for i in range(n):
                        it.a != i
                self.assertGreaterEqual(p.a, n)

    def test_host_set_with_stepped_range(self):
        p = P()
        for step in (5, 3):
            s = [range(0, 30, step), 99]
            for _ in range(20):
                with p.randomize_with() as it:
                    it.a in s
                self.assertTrue(p.a == 99 or (p.a < 30 and p.a % step == 0),
                                p.a)
        pairs = [(10, 12)]
        for _ in range(20):
            with p.randomize_with() as it:
                it.a in pairs           # a (lo, hi) pair is an interval
            self.assertIn(p.a, (10, 11, 12))

    def test_value_passed_to_a_call_is_parsed(self):
        # sorted(it.arr) passes a value, not 'it': the body is parsed, and
        # the grammar rejects the call (it used to run on the legacy path).
        p = P()
        with self.assertRaisesRegex(ConstraintParseError,
                                    "a constraint loop runs over an array "
                                    "field: 'for x in it.arr'"):
            with p.randomize_with() as it:
                all(x > 1 for x in sorted(it.arr))

    def test_inert_body(self):
        # A body with no code: nothing to skip, and nothing constrained.
        p = P()
        with p.randomize_with() as it:
            """Nothing to add."""
        with p.randomize_with() as it:
            pass
        with self.assertRaises(vdc.SolveFailure):
            with p.randomize_with() as it:
                False


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
