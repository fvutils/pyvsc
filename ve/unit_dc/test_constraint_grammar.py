"""
The vdc constraint grammar: which Python constructs a constraint body accepts,
what each one means, and which are rejected.

One test per row of ``doc/notes/vdc_constraint_python_grammar.md``, named
``test_G<nn>_<slug>``, so the spec's G-table is the index of this file.
``G_ROWS`` lists every row; a row whose ledger item (plan
``doc/notes/vdc_constraint_grammar_impl_plan.md`` §9) has not landed yet is
marked with that item, and ``TestGrammarIndex`` keeps the two in step.

Accepted rows check the constraint holds over 20 randomizations and, where a
narrower wrong meaning is possible, that a witness value is still allowed.
Rejected rows check the error is raised when the class is defined and names the
offending ``file:line``.
"""
import os
import re
import unittest

from grammar_util import GrammarCase


# G-ID -> None (tested here) or the plan ledger item that will add its test.
G_ROWS = {
    1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None,
    9: None, 10: None, 11: None, 12: None, 13: None, 14: None, 15: None,
    16: None, 17: None, 18: None, 19: None, 20: None, 21: None, 22: None,
    23: None, 24: None, 25: None, 26: None, 27: None, 28: None, 29: None,
    30: None, 31: None, 32: None, 33: None, 34: None, 35: None, 36: None,
    37: None, 38: None, 39: None, 40: None, 41: None, 42: None, 43: None,
    44: None, 45: None, 46: None, 47: None, 48: None, 49: None, 50: None,
    51: None, 52: None, 53: None, 54: None, 55: None, 56: None,
    57: None, 58: None, 59: None, 60: None, 61: None, 62: None,
    63: None, 64: None, 65: None, 66: None, 67: None, 68: "2.4", 69: None,
    70: None, 71: None, 72: None, 73: None, 74: None, 75: None,
    76: None, 77: None, 78: None, 79: None, 80: "2.7", 81: None, 82: None,
    83: None, 84: None, 85: None, 86: None, 87: None, 88: "2.5", 89: None,
    90: None, 91: None, 92: None, 93: None,
}

_SPEC = os.path.join(os.path.dirname(__file__), "..", "..", "doc", "notes",
                     "vdc_constraint_python_grammar.md")


class TestGrammarIndex(unittest.TestCase):
    """The G-table and this file must not drift apart."""

    def _tested(self):
        ids = set()
        for name in dir(TestConstraintGrammar):
            m = re.match(r"test_G(\d\d)_", name)
            if m:
                ids.add(int(m.group(1)))
        return ids

    def test_every_landed_row_has_a_test(self):
        tested = self._tested()
        done = {g for g, item in G_ROWS.items() if item is None}
        self.assertEqual(sorted(done - tested), [], "rows without a test")
        self.assertEqual(sorted(tested - done), [],
                         "tested rows still marked pending in G_ROWS")

    @unittest.skipUnless(os.path.exists(_SPEC), "spec not present")
    def test_rows_match_spec(self):
        with open(_SPEC) as f:
            spec = {int(g) for g in re.findall(r"^\| G-(\d\d) \|", f.read(), re.M)}
        self.assertEqual(sorted(spec), sorted(G_ROWS))


class TestConstraintGrammar(GrammarCase):

    # -- 2.1 literals and names ---------------------------------------------

    def test_G01_int_literals(self):
        self.accept("""
            self.a == 0x10
            self.b == 0b101
            self.c == 0o17
            self.i == 1_0 - 7
        """, lambda t: (t.a, t.b, t.c, t.i) == (16, 5, 15, 3))

    def test_G02_negative_literal(self):
        self.accept("self.s == -5", lambda t: t.s == -5)

    def test_G03_true_false_in_expression(self):
        self.accept("self.flag == True", lambda t: t.flag == 1)
        self.accept("self.flag == False", lambda t: t.flag == 0)

    def test_G04_non_integer_constants(self):
        for body in ("self.a == 'x'", "self.a == b'x'", "self.a == 1.5",
                     "self.a == 1j", "self.a == None"):
            with self.subTest(body=body):
                self.reject(body, "unsupported constant")

    def test_G05_fstring(self):
        self.reject("f'{self.a}' == '1'", "JoinedStr")

    def test_G06_module_global(self):
        self.accept("self.a == LIMIT", lambda t: t.a == 10)

    def test_G07_closure_variable(self):
        self.accept(None, lambda t: t.a == 7, src="""
            import vsc.dc as vdc

            def make():
                K = 7

                @vdc.dataclass
                class T(vdc.RandClass):
                    a: vdc.u8 = vdc.rand()

                    @vdc.constraint
                    def c_probe(self):
                        self.a == K
                return T

            T = make()
        """)

    def test_G08_enum_member(self):
        self.accept("self.e == E.B", lambda t: t.e == 2)

    def test_G09_class_constant_via_self(self):
        self.accept("self.a == self.MAXV", lambda t: t.a == 20)
        # Folded per subclass: an override changes the value.
        self.accept(None, lambda t: t.a == 30, cls="U", src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                MAXV = 20
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.a == self.MAXV

            class U(T):
                MAXV = 30
        """)

    def test_G10_class_constant_via_class_name(self):
        self.accept("self.a == T.MAXV", lambda t: t.a == 20)
        self.same_model("self.a == T.MAXV", "self.a == self.MAXV")
        # Per subclass, as self.MAXV; a bool; and a collection, by either name.
        self.accept(None, lambda t: t.a == 30 and t.b in (7, 8) and t.c in (7, 8),
                    cls="U", src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                MAXV = 20
                ON = True
                VALS = (1, 2)
                a: vdc.u8 = vdc.rand()
                b: vdc.u8 = vdc.rand()
                c: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.a == T.MAXV
                    if T.ON:
                        self.b in T.VALS
                    self.c in self.VALS
                    self.c != 1

            class U(T):
                MAXV = 30
                VALS = range(7, 9)
        """)
        self.accept(None, unsat=True, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                NONE = []
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.a in self.NONE
        """)
        self.reject("self.a == T.NOPE", "'NOPE' is not an int, bool or enum")
        self.reject("self.a == T.a", "'a' is not an int, bool or enum")
        self.reject("self.a in T.MAXV", "'MAXV' is not an array field or a class")

    def test_G11_unknown_name(self):
        self.reject("self.a == zz", "reference to local/global 'zz'")

    # -- 2.2 arithmetic and bitwise -----------------------------------------

    def test_G12_true_division(self):
        # Python '/' gives a float; it used to mean '//' silently (B5).
        self.reject("self.a / 4 == 3", "no true division; use '//'")
        self.reject("""
            self.b == 1
            self.a == self.c / self.b
        """, "use '//'", line=2)

    def test_G13_floordiv_mod(self):
        self.accept("""
            self.a // 4 == 3
            self.a % 4 == 1
        """, lambda t: t.a == 13)

    def test_G13_signed_div_mod_truncate(self):
        # SV, not Python, for a negative operand (Q7): '//' truncates toward
        # zero and '%' takes the dividend's sign. Python gives -4 and 1 here.
        src = """
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                p: vdc.s8 = vdc.rand()
                q: vdc.s8 = vdc.rand()
                r: vdc.s8 = vdc.rand()
                m: vdc.s8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.p == -7
                    self.q == self.p // 2
                    self.r == self.p // -2
                    self.m == self.p % 2
        """
        self.accept(None, lambda t: (t.q, t.r, t.m) == (-3, 3, -1), src=src)

    def test_G14_add_sub_mul(self):
        self.accept("""
            self.a + self.b == 10
            self.a - self.c == 2
            self.b * 3 == 12
        """, lambda t: (t.a + t.b, t.a - t.c, t.b) == (10, 2, 4))

    def test_G15_power(self):
        self.accept("self.a ** 2 == 49", lambda t: t.a == 7)
        self.same_model("self.a ** 2 == 49", "self.a * self.a == 49")
        self.accept("self.a ** 3 == 125", lambda t: t.a == 5)
        self.accept("self.s ** 2 == 9", lambda t: t.s in (3, -3),
                    witness=lambda it: it.s == -3)
        self.accept("self.a ** 0 == 1")
        self.accept("self.a ** 1 == 9", lambda t: t.a == 9)
        self.accept("self.a == 2 ** 7", lambda t: t.a == 128)
        self.accept("self.a ** E.B == 25", lambda t: t.a == 5)
        # The square is not taken at 8 bits: 16 ** 2 is 256, not 0.
        self.accept("self.a ** 2 == 256", lambda t: t.a == 16)
        for body in ("self.a ** self.b == 8", "self.a ** 9 == 1",
                     "self.a ** -1 == 1"):
            with self.subTest(body=body):
                self.reject(body, "'**' needs a constant exponent from 0 to 8")

    def test_G16_matmul(self):
        self.reject("self.a @ self.b == 1", "unsupported binary operator")

    def test_G17_bitwise(self):
        self.accept("""
            (self.a & 0xF0) == 0x30
            (self.b | 1) == 3
            (self.c ^ 0xFF) == 0xF0
        """, lambda t: (t.a & 0xF0, t.b | 1, t.c) == (0x30, 3, 0x0F),
            witness=lambda it: it.a == 0x3F)

    def test_G18_shifts(self):
        self.accept("""
            (self.a << 1) == 8
            (self.b >> 2) == 1
        """, lambda t: t.a == 4 and t.b >> 2 == 1)

    def test_G18_signed_shift_is_logical(self):
        # '>>' is a logical shift at the context width (32 bits here), not
        # Python's arithmetic shift (Q7): -7 >> 1 is 0x7FFFFFFC, not -4.
        src = """
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                p: vdc.s8 = vdc.rand()
                r: vdc.s16 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.p == -7
                    self.r == BODY
        """
        self.accept(None, lambda t: t.r == 0xFC,
                    src=src.replace("BODY", "(self.p >> 1) & 0xFF"))
        self.accept(None, unsat=True, src=src.replace("BODY", "self.p >> 1"))

    def test_G19_invert(self):
        # Masked: unmasked, ~a is taken at the comparison's width, and the
        # solvers disagree on what that is (spec B8).
        self.accept("(~self.a & 0xFF) == 0xF0", lambda t: t.a == 0x0F)
        # On a comparison, ~ is logical not.
        self.accept("~(self.a == 5)", lambda t: t.a != 5,
                    witness=lambda it: it.a == 6)

    def test_G20_unary_minus(self):
        self.accept("-self.s == 5", lambda t: t.s == -5)
        self.accept("self.a == -self.b + 10", lambda t: t.a == 10 - t.b)
        self.accept("-(-self.a) == 3", lambda t: t.a == 3)
        self.accept("self.s == -self.MAXV", lambda t: t.s == -20)
        self.accept("self.s == -LIMIT", lambda t: t.s == -10)
        # Python's value, not an 8-bit wrap: -a of a u8 is never 0xFF.
        self.accept("-self.a == 0xFF", unsat=True)
        # Unchanged for a literal, including where a constant is required.
        self.accept("self.s in [(-3, -1), -7]", lambda t: -3 <= t.s <= -1 or t.s == -7)

    def test_G21_unary_plus(self):
        self.accept("+self.a == 3", lambda t: t.a == 3)
        self.same_model("+self.a == +3", "self.a == 3")

    # -- 2.3 logical --------------------------------------------------------

    def test_G22_and_or(self):
        self.accept("self.a > 3 and self.a < 6", lambda t: 3 < t.a < 6,
                    witness=lambda it: it.a == 5)
        self.same_model("self.a > 3 and self.a < 6", "(self.a > 3) & (self.a < 6)")
        self.accept("self.a == 1 or self.a == 7", lambda t: t.a in (1, 7),
                    witness=lambda it: it.a == 7)
        self.accept("self.a > 1 and self.a < 9 and self.a != 5",
                    lambda t: 1 < t.a < 9 and t.a != 5)
        self.same_model("self.a == 1 or self.a == 2 or self.a == 3",
                        "(self.a == 1) | (self.a == 2) | (self.a == 3)")
        # 'and' binds tighter than 'or'.
        self.accept("self.a == 1 or self.b == 2 and self.c == 3",
                    lambda t: t.a == 1 or (t.b == 2 and t.c == 3),
                    witness=lambda it: (it.a == 1, it.b == 0))
        # Across lines, inside parentheses.
        self.accept("""
            (self.a == 4
             or self.a == 8)
        """, lambda t: t.a in (4, 8))
        # A non-boolean operand is tested for truth: a != 0, not bit 0.
        self.accept("self.a and self.b == 0", lambda t: t.a != 0 and t.b == 0,
                    witness=lambda it: it.a == 0x80)
        self.accept("self.a == 0 or self.b", lambda t: t.a == 0 or t.b != 0,
                    witness=lambda it: (it.a == 1, it.b == 0x40))
        # A class constant folds away.
        self.accept("self.ON and self.a == 3", lambda t: t.a == 3)
        self.accept("self.a == 3 and False", unsat=True)
        # In an expression, not only as a statement.
        self.accept("self.flag == (self.a > 3 and self.a < 6)",
                    lambda t: t.flag == (3 < t.a < 6),
                    witness=lambda it: it.a == 4)

    def test_G23_not(self):
        self.accept("not (self.a == 5)", lambda t: t.a != 5,
                    witness=lambda it: it.a == 4)
        self.accept("not self.flag", lambda t: t.flag == 0)
        # On a wide operand, 'not' is a truth test, where '~' inverts each bit.
        self.accept("not self.a", lambda t: t.a == 0)
        self.accept("not (self.a > 3 and self.a < 6)",
                    lambda t: not 3 < t.a < 6, witness=lambda it: it.a == 6)
        self.accept("not not (self.a == 5)", lambda t: t.a == 5)
        self.accept("not self.ON", unsat=True)
        # '~' on a comparison is logical not, so its 'not' undoes it.
        self.accept("not ~(self.a > 3)", lambda t: t.a > 3,
                    witness=lambda it: it.a == 4)
        self.accept("self.a > 3 and ~(self.a > 5)", lambda t: 3 < t.a <= 5,
                    witness=lambda it: it.a == 5)

    def test_G25_conditional_expression(self):
        self.accept("self.a == (1 if self.flag else 2)",
                    lambda t: t.a == (1 if t.flag else 2),
                    witness=lambda it: it.flag == 1)
        # A wide condition is a truth test.
        self.accept("self.a == (1 if self.b else 2)",
                    lambda t: t.a == (1 if t.b else 2),
                    witness=lambda it: it.b == 0x80)
        # The arms take the wider width: 300 is never an 8-bit value.
        self.accept("self.a == (300 if self.flag else 2)",
                    lambda t: t.flag == 0 and t.a == 2)
        self.accept("self.c == (self.a + 0x100 if self.flag else 3) - 0xF0",
                    lambda t: t.flag == 1 and t.c == t.a + 0x10)
        # Signed arms stay signed.
        self.accept("(self.s if self.flag else -1) == -4",
                    lambda t: t.flag == 1 and t.s == -4)
        # Nested; and a class constant picks the arm when the type is built.
        self.accept("self.a == (1 if self.b < 10 else 2 if self.b < 20 else 3)",
                    lambda t: t.a == (1 if t.b < 10 else 2 if t.b < 20 else 3))
        self.same_model("self.a == (1 if self.ON else 2)", "self.a == 1")
        # As a statement it is an if/else; with boolean arms, it is logic.
        self.same_model("(self.a == 1) if self.flag else (self.a == 2)", """
            if self.flag:
                self.a == 1
            else:
                self.a == 2
        """)
        self.accept("self.flag == ((self.a == 1) if self.b else (self.a == 2))",
                    lambda t: t.flag == (t.a == (1 if t.b else 2)),
                    witness=lambda it: (it.flag == 1, it.b == 0))

    # -- 2.4 comparisons ----------------------------------------------------

    def test_G26_comparisons(self):
        self.accept("""
            self.a != 0
            self.a < 100
            self.a <= 99
            self.b > 3
            self.b >= 4
            self.c == 7
        """, lambda t: 0 < t.a < 100 and t.b > 3 and t.c == 7)

    def test_G27_chained_comparison(self):
        self.accept("1 < self.a < 5", lambda t: 1 < t.a < 5,
                    witness=lambda it: it.a == 4)
        self.accept("self.a == self.b == self.c", lambda t: t.a == t.b == t.c)

    def test_G28_in_inside_chain(self):
        # Python: 0 < a in S is (0 < a) and (a in S).
        self.accept("0 < self.a in [0, 4, 9]", lambda t: t.a in (4, 9),
                    witness=lambda it: it.a == 9)
        self.accept("self.b < self.a not in range(0, 200)",
                    lambda t: t.b < t.a and t.a >= 200)
        self.same_model("1 < self.a in {3, 5}", "(1 < self.a) & (self.a in {3, 5})")
        # The set is also the left side of a later comparison, as in Python
        # (a in S == b is (a in S) and (S == b)), and a set is not a value.
        self.reject("self.a in [1, 2] < 3", "unsupported expression List")
        self.reject("self.a in ALLOWED == self.b", "not an integer/enum constant")

    def test_G24_bitwise_in_chain(self):
        # Python reads these as chains: a > (3 & a) < 6 (B7).
        for body, ops in (("self.a > 3 & self.a < 6", "'&' binds tighter than '>'"),
                          ("self.a == 1 | self.b == 2", "'|' binds tighter than '=='"),
                          ("self.a < 3 ^ self.b > 1", "'^' binds tighter than '<'"),
                          ("1 < self.a < 6 & self.b", "'&' binds tighter than '<'")):
            with self.subTest(body=body):
                self.reject(body, ops)
        self.reject("""
            self.b == 1
            (self.a > 3 &
                self.a < 6)
        """, "chained comparison", line=2)
        # Parenthesized, the meaning is the one written, so it is accepted.
        self.accept("(self.a > 3) & (self.a < 6)", lambda t: 3 < t.a < 6)
        self.accept("1 < (self.a & 0xF) < 6", lambda t: 1 < (t.a & 0xF) < 6)
        self.accept("1 < ( self.a | 1 ) <= 3", lambda t: 1 < (t.a | 1) <= 3)
        self.accept("""
            1 < \\
                (self.a & 7) < 3
        """, lambda t: (t.a & 7) == 2)
        # Not a chain: '&' binds tighter, and that is the meaning.
        self.accept("self.a & 0xF == 3", lambda t: (t.a & 0xF) == 3)

    def test_G29_is(self):
        self.reject("self.a is self.b", "unsupported comparison")
        self.reject("self.a is not None", "unsupported comparison")

    def test_G30_literal_on_left(self):
        self.accept("5 == self.a", lambda t: t.a == 5)

    # -- 2.5 set membership -------------------------------------------------

    def test_G31_list_tuple_literal(self):
        self.accept("self.a in [1, 2, 3]", lambda t: t.a in (1, 2, 3))
        self.accept("self.a in (1, 2, 3)", lambda t: t.a in (1, 2, 3))
        self.accept("self.a not in [0, 1, 2]", lambda t: t.a not in (0, 1, 2))
        self.accept("self.a in [self.b, self.c + 1]",
                    lambda t: t.a in (t.b, t.c + 1))
        self.accept("self.e in [E.A, E.B]", lambda t: t.e in (1, 2))
        self.accept("5 in [self.a, self.b]", lambda t: 5 in (t.a, t.b))
        self.accept("self.a + 1 in [3, 4]", lambda t: t.a in (2, 3))

    def test_G32_tuple_element_is_inclusive_range(self):
        self.accept("self.a in [1, (10, 12)]",
                    lambda t: t.a == 1 or 10 <= t.a <= 12,
                    witness=lambda it: it.a == 12)

    def test_G33_set_literal(self):
        self.accept("self.a in {1, 2, 3}", lambda t: t.a in (1, 2, 3),
                    witness=lambda it: it.a == 3)
        self.accept("self.a not in {0, 1}", lambda t: t.a > 1)
        self.same_model("self.a in {1, 2}", "self.a in [1, 2]")
        self.accept("self.a in {self.b, 7}", lambda t: t.a in (t.b, 7))

    def test_G34_range_is_half_open(self):
        self.accept("self.a in range(3, 6)", lambda t: 3 <= t.a < 6,
                    witness=lambda it: it.a == 5)
        self.accept("self.a in range(4)", lambda t: t.a < 4)
        self.accept("""
            self.a in range(3, 6)
            self.a == 6
        """, unsat=True)

    def test_G35_stepped_range(self):
        self.accept("self.a in range(0, 20, 4)", lambda t: t.a in range(0, 20, 4),
                    witness=lambda it: it.a == 16)
        self.accept("""
            self.a in range(0, 20, 4)
            self.a == 20
        """, unsat=True)
        self.accept("self.a in range(3, 30, 9)", lambda t: t.a in (3, 12, 21),
                    witness=lambda it: it.a == 21)
        self.accept("self.a in range(10, 0, -3)", lambda t: t.a in (10, 7, 4, 1),
                    witness=lambda it: it.a == 1)
        self.accept("self.s in range(-8, 8, 4)", lambda t: t.s in (-8, -4, 0, 4),
                    witness=lambda it: it.s == -8)
        self.accept("self.a not in range(0, 256, 2)", lambda t: t.a % 2 == 1)
        self.accept("self.a in [range(0, 10, 5), 7]", lambda t: t.a in (0, 5, 7),
                    witness=lambda it: it.a == 7)
        self.accept("self.a.inside(range(1, 9, 2))", lambda t: t.a in (1, 3, 5, 7))
        # A field endpoint; a step of 1 is a plain range.
        self.accept("self.a in range(self.b, self.b + 9, 3)",
                    lambda t: t.a in range(t.b, t.b + 9, 3))
        self.same_model("self.a in range(2, 5, 1)", "self.a in range(2, 5)")
        self.reject("self.a in range(0, 10, self.b)",
                    "step must be a non-zero constant")
        self.reject("self.a in range(0, 10, 0)", "step must be a non-zero constant")

    def test_G36_r_slice_is_inclusive(self):
        self.accept("self.a in vdc.r[3:6]", lambda t: 3 <= t.a <= 6,
                    witness=lambda it: it.a == 6)
        self.accept("self.a in vdc.r[1:2, 8:9]", lambda t: t.a in (1, 2, 8, 9))

    def test_G37_rangelist_rng(self):
        self.accept("self.a in vdc.rangelist(1, (10, 12))",
                    lambda t: t.a == 1 or 10 <= t.a <= 12)
        self.accept("self.a in [vdc.rng(10, 12)]", lambda t: 10 <= t.a <= 12,
                    witness=lambda it: it.a == 12)

    def test_G38_in_array_field(self):
        self.accept("self.a in self.arr", lambda t: t.a in t.arr,
                    witness=lambda it: it.a == 77)
        self.accept("""
            self.arr[0] == 5
            self.arr[1] == 6
            self.arr[2] == 5
            self.arr[3] == 6
            self.a in self.arr
        """, lambda t: t.a in (5, 6))
        self.accept("self.a not in self.arr", lambda t: t.a not in t.arr)
        self.accept("self.a.inside(self.arr)", lambda t: t.a in t.arr)
        # A non-rand array: membership in its current values.
        self.accept(None, lambda t: t.a in (4, 9), src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()
                vals: list[vdc.u8] = vdc.field(default_factory=lambda: [4, 9])

                @vdc.constraint
                def c_probe(self):
                    self.a in self.vals
        """)
        # A variable-size array: only the active elements count.
        self.accept(None, lambda t: 1 <= len(t.arr) and t.a in t.arr, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()
                arr: list[vdc.u8] = vdc.rand(max_size=4)

                @vdc.constraint
                def c_probe(self):
                    self.arr.size > 0
                    self.arr.size <= 4
                    self.a in self.arr
        """)
        self.reject("self.a in self.b", "'b' is not an array field or a class "
                    "attribute holding")

    def test_G39_named_constant_collection(self):
        self.accept("self.a in ALLOWED", lambda t: t.a in (1, 3, 5),
                    witness=lambda it: it.a == 5)
        self.accept("self.a in ALLOWED_SET", lambda t: t.a in (1, 3, 5))
        self.accept("self.a in ALLOWED_RANGE", lambda t: t.a in (1, 2, 3),
                    witness=lambda it: it.a == 3)
        self.accept("self.a not in ALLOWED", lambda t: t.a not in (1, 3, 5))
        self.accept("self.a.inside(ALLOWED)", lambda t: t.a in (1, 3, 5))
        # Enum members; a closure; a class attribute by class name; a frozenset.
        self.accept(None, lambda t: t.a in (2, 4) and t.b in (8, 9) and t.c == 6,
                    src="""
            import enum
            import vsc.dc as vdc

            class E(enum.IntEnum):
                A = 2
                B = 4

            class K:
                EVENS = frozenset({6})

            def make():
                PAIR = (8, 9)

                @vdc.dataclass
                class T(vdc.RandClass):
                    a: vdc.u8 = vdc.rand()
                    b: vdc.u8 = vdc.rand()
                    c: vdc.u8 = vdc.rand()

                    @vdc.constraint
                    def c_probe(self):
                        self.a in [E.A, E.B]
                        self.b in PAIR
                        self.c in K.EVENS
                return T

            T = make()
        """)
        # Read when the class is defined.
        self.accept(None, lambda t: t.a in (1, 2), src="""
            import vsc.dc as vdc

            VALS = [1, 2]

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.a in VALS

            VALS.append(3)
        """)
        self.accept(None, unsat=True, src="""
            import vsc.dc as vdc

            NONE = []

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.a in NONE
        """)
        self.reject("self.a in LIMIT", "value set must be")

    def test_G40_starred_collection(self):
        self.accept("self.a in [*ALLOWED, 9]", lambda t: t.a in (1, 3, 5, 9),
                    witness=lambda it: it.a == 9)
        self.accept("self.a in {*ALLOWED_RANGE, *ALLOWED_SET}",
                    lambda t: t.a in (1, 2, 3, 5))
        self.reject("self.a in [*self.arr, 9]", "only a constant collection")

    def test_G41_enum_class(self):
        self.reject("self.e in E", "value set must be")

    def test_G42_inside_methods(self):
        self.accept("self.a.inside(vdc.rangelist(1, 2))", lambda t: t.a in (1, 2))
        self.accept("self.a.not_inside(vdc.rangelist(0, 1))",
                    lambda t: t.a not in (0, 1))
        self.accept("self.a.outside([0, 1])", lambda t: t.a not in (0, 1))

    def test_G43_other_call_in_set(self):
        self.reject("self.a in helper(1)", "unsupported call 'helper'")

    # -- 2.6 subscripts, attributes, reductions -----------------------------

    def test_G44_bit_select(self):
        self.accept("""
            self.a[0] == 1
            self.a[7] == 0
        """, lambda t: t.a & 1 and not t.a & 0x80)
        # A random bit index is chosen by the solve (B1).
        self.accept("""
            self.a[self.i] == 1
            self.i == 2
        """, lambda t: t.i == 2 and (t.a >> 2) & 1)
        self.accept("self.a[self.i] == 0",
                    lambda t: not (t.a >> t.i) & 1,
                    witness=lambda it: (it.i == 3, it.a == 0xF7))

    def test_G45_part_select_hi_lo(self):
        self.accept("self.a[7:4] == 0xA", lambda t: t.a >> 4 == 0xA)
        self.accept("self.a[3:3] == 1", lambda t: (t.a >> 3) & 1)
        self.accept("self.a[LIMIT - 3:LIMIT - 6] == 0xF", lambda t: (t.a >> 4) == 0xF)
        # Python slice order is rejected, not read as an empty slice.
        self.reject("self.a[4:7] == 0xA", "write [7:4]")
        self.reject("self.a[0:LIMIT - 3] == 1", "write [7:0]")

    def test_G46_part_select_step_or_open(self):
        self.reject("self.a[7:4:1] == 1", "part-select with a step")
        self.reject("self.a[7:] == 1", "explicit bounds")

    def test_G47_array_constant_index(self):
        self.accept("self.arr[1] == 7", lambda t: t.arr[1] == 7)

    def test_G48_negative_index(self):
        # Python's meaning: counted from the end.
        self.accept("""
            self.arr[-1] == 7
            self.arr[-4] == 3
        """, lambda t: t.arr[3] == 7 and t.arr[0] == 3)
        self.accept("self.objs[-1].x == 5", lambda t: t.objs[1].x == 5)
        # A random-size array counts from its solved size, not the previous one.
        self.accept(None, lambda t: t.arr[-1] == 7 and t.objs[-1].x == 9,
                    n=40, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class Sub(vdc.RandClass):
                x: vdc.u8 = vdc.rand()

            @vdc.dataclass
            class T(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(max_size=5)
                objs: list[Sub] = vdc.rand(max_size=3)

                @vdc.constraint
                def c_probe(self):
                    self.arr.size > 0
                    self.arr.size <= 5
                    self.arr[-1] == 7
                    self.objs.size > 0
                    self.objs[-1].x == 9
        """)

    def test_G49_array_symbolic_index(self):
        # The first solve of a fresh type uses the solved index (B1).
        self.accept("""
            self.arr[self.i] == 9
            self.i == 2
        """, lambda t: t.i == 2 and t.arr[2] == 9)
        self.accept("self.arr[self.i] == 9", lambda t: t.arr[t.i] == 9,
                    witness=lambda it: it.i == 3)

    def test_G50_array_slice(self):
        self.reject("self.arr[0:2] == 0", "array slices are not supported")
        # A nested array is caught when the model is lowered.
        mod = self.build(src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class Inner(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(size=4)

            @vdc.dataclass
            class T(vdc.RandClass):
                sub: Inner = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    self.sub.arr[1:0] == 0
        """)
        with self.assertRaisesRegex(TypeError, "array slices are not supported"):
            mod.T().randomize()

    def test_G51_nested_composite(self):
        self.accept("self.sub.x == 4", lambda t: t.sub.x == 4)
        self.accept("self.objs[1].x == 4", lambda t: t.objs[1].x == 4)
        self.accept("""
            self.objs[self.i].x == 4
            self.i == 1
        """, lambda t: t.i == 1 and t.objs[1].x == 4)

    def test_G52_size_sum(self):
        self.accept("self.arr.size == 4", lambda t: len(t.arr) == 4)
        self.accept("self.arr.sum == 10", lambda t: sum(t.arr) == 10)

    def test_G53_len(self):
        self.accept("len(self.arr) == 4", lambda t: len(t.arr) == 4)
        self.same_model("len(self.arr) == 4", "self.arr.size == 4")
        self.accept(None, lambda t: 2 <= len(t.arr) <= 3, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(max_size=4)

                @vdc.constraint
                def c_probe(self):
                    len(self.arr) > 1
                    len(self.arr) < 4
        """)
        self.reject("len(self.a) == 1", "len() in a constraint takes an array field")

    def test_G54_sum(self):
        self.accept("sum(self.arr) == 10", lambda t: sum(t.arr) == 10)
        self.same_model("sum(self.arr) == 10", "self.arr.sum == 10")
        self.reject("sum(self.arr, 1) == 10", "sum() in a constraint takes one array")
        self.reject("sum([self.a, self.b]) == 3", "takes an array field")

    def test_G55_product(self):
        self.accept("self.arr.product == 24",
                    lambda t: t.arr[0] * t.arr[1] * t.arr[2] * t.arr[3] == 24)
        self.same_model("math.prod(self.arr) == 6", "self.arr.product == 6")
        self.accept(None, lambda t: t.arr[0] * t.arr[1] * t.arr[2] == 30,
                    src="""
            from math import prod
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(size=3)

                @vdc.constraint
                def c_probe(self):
                    prod(self.arr) == 30
        """)
        self.reject("math.prod(self.a) == 1", "takes an array field")

    def test_G56_scalar_min_max(self):
        self.accept("min(self.a, self.b) == 3", lambda t: min(t.a, t.b) == 3,
                    witness=lambda it: it.b == 3)
        self.accept("max(self.a, self.b, self.c) == 7",
                    lambda t: max(t.a, t.b, t.c) == 7,
                    witness=lambda it: it.c == 7)
        self.accept("min(self.s, 0) == -4", lambda t: t.s == -4)
        self.accept("max(self.a, 10) == 10", lambda t: t.a <= 10)
        self.reject("min(self.a) == 3", "scalar min() needs two or more arguments")
        self.reject("max(self.a, self.b, key=abs) == 3", "no keyword arguments")
        self.reject("max(*self.arr) == 3", "no *arguments")
        # A name the module rebinds is not the builtin.
        self.reject(None, "unsupported call", line=13, src="""
            import vsc.dc as vdc

            def max(*a):
                return 0

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    max(self.a, 1) == 3
        """)

    def test_G57_array_min_max(self):
        self.reject("min(self.arr) == 3", "min() over an array is not supported yet")
        self.reject("max(self.arr) > 3", "max() over an array is not supported yet")

    def test_G58_abs(self):
        self.accept("abs(self.s) == 5", lambda t: t.s in (5, -5),
                    witness=lambda it: it.s == -5)
        # Python's value: abs(-128) is 128, not an 8-bit wrap to -128.
        self.accept("abs(self.s) == 128", lambda t: t.s == -128)
        self.accept("abs(self.s) > 126", lambda t: t.s in (127, -127, -128))
        self.accept("abs(self.a) == 200", lambda t: t.a == 200)
        # An unsigned operand is never < 0, so abs() of it is the operand: as
        # in SV, a - b of unsigned fields is unsigned (it wraps), and only
        # a - b == 3 satisfies this, not b - a == 3.
        self.accept("abs(self.a - self.b) == 3", lambda t: t.a - t.b == 3)
        # Signed operands give Python's answer.
        self.accept("abs(self.s - 3) == 5", lambda t: t.s in (8, -2),
                    witness=lambda it: it.s == -2)

    def test_G59_all(self):
        # As a statement it is a foreach: the same model.
        self.accept("all(x > 100 for x in self.arr)",
                    lambda t: all(x > 100 for x in t.arr))
        self.same_model("all(x > 100 for x in self.arr)", """
            with vdc.foreach(self.arr) as x:
                x > 100
        """)
        self.accept("all(self.arr[i] == i for i in range(len(self.arr)))",
                    lambda t: list(t.arr) == [0, 1, 2, 3])
        self.accept("all(self.arr[i] == i + 1 for i in range(self.arr.size))",
                    lambda t: list(t.arr) == [1, 2, 3, 4])
        self.accept("all(x == 2 * i for i, x in enumerate(self.arr))",
                    lambda t: list(t.arr) == [0, 2, 4, 6])
        self.accept("all(x == 5 for i, x in enumerate(self.arr) if i != 2)",
                    lambda t: [t.arr[0], t.arr[1], t.arr[3]] == [5, 5, 5],
                    witness=lambda it: it.c == 0)
        self.accept("all(o.x < 10 for o in self.objs)",
                    lambda t: all(o.x < 10 for o in t.objs))
        # In an expression, unrolled over the elements.
        self.accept("self.flag == all(x < 128 for x in self.arr)",
                    lambda t: t.flag == all(x < 128 for x in t.arr),
                    witness=lambda it: it.flag == 1)
        self.accept("not all(x < 200 for x in self.arr)",
                    lambda t: any(x >= 200 for x in t.arr))
        for body in ("all(x > 1 for x in self.a)",
                     "all(x > 1 for x in [1, 2])",
                     "all(x > 1 for x in range(4))",
                     "all(x > y for x in self.arr for y in self.arr)",
                     "all(x > 1 for x in sorted(self.arr))"):
            with self.subTest(body=body):
                self.reject(body, "a constraint loop runs over an array field"
                            if "for y" not in body else "one 'for' over an array")
        self.reject("all([self.a > 1])", "takes a generator over an array")

    def test_G60_any(self):
        self.accept("any(x == 7 for x in self.arr)", lambda t: 7 in t.arr)
        self.accept("""
            any(x == 7 for x in self.arr)
            self.arr[0] != 7
            self.arr[1] != 7
            self.arr[2] != 7
        """, lambda t: t.arr[3] == 7)
        self.accept("not any(x == 7 for x in self.arr)", lambda t: 7 not in t.arr)
        self.accept("any(x > 250 for i, x in enumerate(self.arr) if i > 1)",
                    lambda t: t.arr[2] > 250 or t.arr[3] > 250)
        self.accept("any(o.x == 3 for o in self.objs)",
                    lambda t: 3 in [o.x for o in t.objs])
        self.accept("self.flag == any(x == 0 for x in self.arr)",
                    lambda t: t.flag == (0 in t.arr), witness=lambda it: it.flag == 1)
        # A random-size composite array: only the active elements count.
        self.accept(None, lambda t: 1 <= len(t.objs) <= 3
                    and 9 in [o.x for o in t.objs], src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class Sub(vdc.RandClass):
                x: vdc.u8 = vdc.rand()

            @vdc.dataclass
            class T(vdc.RandClass):
                objs: list[Sub] = vdc.rand(max_size=3)

                @vdc.constraint
                def c_probe(self):
                    self.objs.size > 0
                    any(o.x == 9 for o in self.objs)
        """)
        # A random-size scalar array is not allocated before its size is
        # solved, so the expression form is not supported yet.
        mod = self.build(None, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(max_size=4)

                @vdc.constraint
                def c_probe(self):
                    self.arr.size > 0
                    self.arr.size <= 4
                    any(x == 9 for x in self.arr)
        """)
        with self.assertRaisesRegex(NotImplementedError, "not supported yet"):
            mod.T().randomize()
        # The statement form is a foreach, which a random-size array supports.
        self.accept(None, lambda t: all(x > 9 for x in t.arr), src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                arr: list[vdc.u8] = vdc.rand(max_size=4)

                @vdc.constraint
                def c_probe(self):
                    self.arr.size <= 4
                    all(x > 9 for x in self.arr)
        """)

    def test_G61_bool(self):
        self.accept("bool(self.a) == self.flag", lambda t: (t.a != 0) == t.flag,
                    witness=lambda it: it.a == 0x80)
        self.accept("bool(self.a)", lambda t: t.a != 0)
        self.same_model("bool(self.a > 3)", "self.a > 3")

    def test_G62_casts(self):
        for body in ("int(self.a) == 5", "float(self.a) == 5",
                     "str(self.a) == '5'"):
            with self.subTest(body=body):
                self.reject(body, "unsupported call in expression")

    def test_G63_comprehensions(self):
        for body, frag in (("[x < 10 for x in self.arr]", "ListComp"),
                           ("{x < 10 for x in self.arr}", "SetComp"),
                           ("{x: 1 for x in self.arr}", "DictComp"),
                           ("(x < 10 for x in self.arr)", "GeneratorExp")):
            with self.subTest(body=body):
                self.reject(body, frag)

    def test_G64_user_function(self):
        self.reject("helper(self.a) == 5", "unsupported call in expression")
        self.reject("print(self.a)", "unsupported call in expression")

    def test_G65_generic_reference(self):
        self.accept(None, lambda t: t.a < 10, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint.generic
                def small(self, hi):
                    self.a < hi

                @vdc.constraint
                def c_probe(self):
                    self.small(10)
        """)

    def test_G66_lambda_walrus_yield(self):
        self.reject("(lambda: self.a)() == 1", "unsupported call in expression")
        self.reject("(y := self.a) == 1", "NamedExpr")
        self.reject("yield self.a", "Yield")

    # -- 3. statements ------------------------------------------------------

    def test_G67_expression_statement(self):
        self.accept("self.a == 5", lambda t: t.a == 5)

    def test_G69_constant_statement(self):
        self.accept("""
            True
            self.a == 5
        """, lambda t: t.a == 5)
        self.accept("False", unsat=True)
        self.accept("""
            self.a == 5
            self.MAXV == 21
        """, unsat=True)

    def test_G70_for_element(self):
        self.accept("""
            for x in self.arr:
                x > 100
        """, lambda t: all(x > 100 for x in t.arr))
        self.same_model("""
            for x in self.arr:
                x > 100
        """, """
            with vdc.foreach(self.arr) as x:
                x > 100
        """)
        self.accept("""
            for x in self.arr:
                if x > 128:
                    x % 2 == 0
                x != self.a
        """, lambda t: all((x <= 128 or x % 2 == 0) and x != t.a for x in t.arr))

    def test_G71_for_index(self):
        self.accept("""
            for i in range(len(self.arr)):
                self.arr[i] == i * 3
        """, lambda t: list(t.arr) == [0, 3, 6, 9])
        self.same_model("""
            for i in range(self.arr.size):
                self.arr[i] == i
        """, """
            with vdc.foreach(self.arr, idx=True) as i:
                self.arr[i] == i
        """)
        # Neighbours: the classic idiom.
        self.accept("""
            for i in range(len(self.arr)):
                if i > 0:
                    self.arr[i] > self.arr[i - 1]
        """, lambda t: all(t.arr[k] > t.arr[k - 1] for k in range(1, 4)))

    def test_G72_for_enumerate(self):
        self.accept("""
            for i, x in enumerate(self.arr):
                x == i + 10
        """, lambda t: list(t.arr) == [10, 11, 12, 13])
        self.same_model("""
            for i, x in enumerate(self.arr):
                x == i
        """, """
            with vdc.foreach(self.arr, idx=True, it=True) as (i, x):
                x == i
        """)

    def test_G73_for_composite(self):
        self.accept("""
            for o in self.objs:
                o.x < 10
                o.x != self.a
        """, lambda t: all(o.x < 10 and o.x != t.a for o in t.objs))
        self.accept("""
            for i, o in enumerate(self.objs):
                o.x == i + 1
        """, lambda t: [o.x for o in t.objs] == [1, 2])

    def test_G74_for_constant_iterable(self):
        # Unrolled: the body once per value, the name a constant in it.
        self.accept("""
            for i in range(3):
                self.arr[i] == i + 1
        """, lambda t: list(t.arr[:3]) == [1, 2, 3])
        self.same_model("""
            for i in range(2):
                self.arr[i] == i
        """, """
            self.arr[0] == 0
            self.arr[1] == 1
        """)
        self.accept("""
            for v in ALLOWED:
                self.a != v
        """, lambda t: t.a not in (1, 3, 5))
        self.accept("""
            for i in range(1, LIMIT - 6):
                self.arr[i] > self.arr[i - 1]
        """, lambda t: t.arr[0] < t.arr[1] < t.arr[2] < t.arr[3])
        self.accept("""
            for k in range(0, 8, 2):
                self.a[k] == 0
        """, lambda t: t.a & 0x55 == 0)
        self.accept("""
            for e in [E.A, E.C]:
                self.e != e
        """, lambda t: t.e == 2)
        self.accept("""
            for lo, hi in ((0, 1), (2, 3)):
                self.arr[lo] < self.arr[hi]
        """, lambda t: t.arr[0] < t.arr[1] and t.arr[2] < t.arr[3])
        # Tuple targets; nested inside a foreach.
        self.accept(None, lambda t: t.a == 4 and t.b == 9, src="""
            import vsc.dc as vdc

            PAIRS = [(4, 9)]

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()
                b: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c_probe(self):
                    for x, y in PAIRS:
                        self.a == x
                        self.b == y
        """)
        self.accept("""
            for x in self.arr:
                for v in ALLOWED_SET:
                    x != v
        """, lambda t: not set(t.arr) & {1, 3, 5})
        self.reject("""
            for i in range(2000):
                self.a != i
        """, "at most 1024 iterations")

    def test_G75_nested_for(self):
        self.accept("""
            for i in range(len(self.arr)):
                for j in range(len(self.arr)):
                    if i < j:
                        self.arr[i] < self.arr[j]
        """, lambda t: list(t.arr) == sorted(t.arr) and len(set(t.arr)) == 4)
        self.accept("""
            for o in self.objs:
                for x in self.arr:
                    o.x != x
        """, lambda t: not {o.x for o in t.objs} & set(t.arr))
        # The loop name is bound only inside its body.
        self.reject("""
            for x in self.arr:
                x > 1
            x < 5
        """, "reference to local/global 'x'", line=3)

    def test_G77_while(self):
        self.reject("while self.a < 3:\n    pass", "While")

    def test_G76_rejected_for(self):
        forms = "a constraint loop runs over an array field: 'for x in self.arr'"
        for body in ("for x in zip(self.arr, self.arr):\n    x > 1",
                     "for x in reversed(self.arr):\n    x > 1",
                     "for x in sorted(self.arr):\n    x > 1",
                     "for x in self.arr[1:]:\n    x > 1",
                     "for i, x in self.arr:\n    x > 1",
                     "for self.a in self.arr:\n    self.a > 1",
                     "for x in self.a:\n    x > 1",
                     "for i in range(len(self.arr), 0, -1):\n    self.arr[i] > 1",
                     "for i in range(self.a):\n    self.arr[i] > 1"):
            with self.subTest(body=body):
                self.reject(body, forms)
        self.reject("""
            for x in self.arr:
                x > 1
            else:
                self.a == 1
        """, "a constraint 'for' has no 'else'")
        for kw in ("break", "continue"):
            with self.subTest(kw=kw):
                self.reject("""
                    for x in self.arr:
                        if x > 1:
                            %s
                """ % kw, "'%s' has no meaning in a constraint loop" % kw,
                            line=3)

    def test_G78_if_elif_else(self):
        self.accept("""
            if self.flag:
                self.a == 1
            else:
                self.a == 2
        """, lambda t: t.a == (1 if t.flag else 2))
        self.accept("""
            if self.b < 10:
                self.a == 1
            elif self.b < 20:
                self.a == 2
            else:
                self.a == 3
        """, lambda t: t.a == (1 if t.b < 10 else 2 if t.b < 20 else 3))
        # No else: an implication.
        self.accept("""
            if self.b > 100:
                self.a == 1
        """, lambda t: t.b <= 100 or t.a == 1,
            witness=lambda it: (it.b == 50, it.a == 9))
        # A multi-bit condition is a truth test.
        self.accept("""
            if self.b:
                self.a == 1
            else:
                self.a == 2
        """, lambda t: t.a == (1 if t.b else 2))

    def test_G79_if_condition_logical(self):
        self.accept("""
            if self.a > 3 and self.flag:
                self.b == 1
            else:
                self.b == 2
        """, lambda t: t.b == (1 if t.a > 3 and t.flag else 2),
            witness=lambda it: (it.a == 9, it.flag == 1, it.b == 1))
        self.accept("""
            if not self.flag:
                self.b == 1
            elif self.a == 1 or self.a == 2:
                self.b == 2
        """, lambda t: (t.b == 1) if not t.flag else
            (t.b == 2 if t.a in (1, 2) else True),
            witness=lambda it: (it.flag == 1, it.a == 2))
        self.accept("""
            with vdc.if_then(self.a < 5 or not self.flag):
                self.b == 7
        """, lambda t: t.b == 7 if (t.a < 5 or not t.flag) else True)
        self.accept("""
            with vdc.implies(not (self.a == 0)):
                self.b == 3
        """, lambda t: t.a == 0 or t.b == 3,
            witness=lambda it: it.a == 0x80)

    def test_G81_with_if_then(self):
        self.accept("""
            with vdc.if_then(self.flag == 1):
                self.a == 1
            with vdc.else_if(self.b == 0):
                self.a == 2
            with vdc.else_then:
                self.a == 3
        """, lambda t: t.a == (1 if t.flag else 2 if t.b == 0 else 3))

    def test_G82_with_implies(self):
        self.accept("""
            with vdc.implies(self.flag == 1):
                self.a == 1
        """, lambda t: not t.flag or t.a == 1,
            witness=lambda it: (it.flag == 0, it.a == 9))

    def test_G83_with_foreach(self):
        self.accept("""
            with vdc.foreach(self.arr) as x:
                x < 10
        """, lambda t: all(x < 10 for x in t.arr))
        self.accept("""
            with vdc.foreach(self.arr, idx=True) as i:
                self.arr[i] == i
        """, lambda t: list(t.arr) == [0, 1, 2, 3])
        self.accept("""
            with vdc.foreach(self.arr, idx=True, it=True) as (i, x):
                x == i + 1
        """, lambda t: list(t.arr) == [1, 2, 3, 4])
        self.accept("""
            with vdc.foreach(self.arr, idx=True) as i:
                if i > 0:
                    self.arr[i] > self.arr[i - 1]
        """, lambda t: all(t.arr[k] > t.arr[k - 1] for k in range(1, 4)))

    def test_G84_with_other(self):
        self.reject("""
            with vdc.if_then(self.flag == 1), vdc.implies(self.a == 1):
                pass
        """, "single context manager")
        self.reject("""
            with open('x'):
                pass
        """, "unsupported with-context 'open'")

    def test_G85_statement_helpers(self):
        self.accept("vdc.soft(self.a == 5)", lambda t: t.a == 5)
        self.accept("""
            vdc.unique(self.a, self.b, self.c)
            self.a < 3
            self.b < 3
            self.c < 3
        """, lambda t: len({t.a, t.b, t.c}) == 3)
        self.accept("""
            vdc.unique(self.arr)
            with vdc.foreach(self.arr) as x:
                x < 4
        """, lambda t: sorted(t.arr) == [0, 1, 2, 3])
        self.accept("""
            vdc.solve_order(self.flag, self.a)
            if self.flag:
                self.a == 1
        """, lambda t: not t.flag or t.a == 1)
        self.accept("vdc.dist(self.a, [vdc.weight(1, 10), vdc.weight((2, 4), 20)])",
                    lambda t: 1 <= t.a <= 4)

    def test_G86_pass(self):
        self.accept("""
            pass
            self.a == 5
        """, lambda t: t.a == 5)

    def test_G87_string_statement(self):
        self.accept('''
            """A docstring."""
            self.a == 5
            "a note"
            self.b == 6
        ''', lambda t: (t.a, t.b) == (5, 6))
        # A value generic may have a docstring too.
        self.accept(None, lambda t: t.a == 4, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint.value
                def twice(self, v):
                    'Twice v.'
                    return v + v

                @vdc.constraint
                def c_probe(self):
                    self.twice(self.a) == 8
        """)

    def test_G89_assignment(self):
        for body in ("self.a = 5", "self.a += 1", "x: int = 1"):
            with self.subTest(body=body):
                self.reject(body, "unsupported statement")

    def test_G90_local_binding(self):
        self.reject("""
            lo = self.b + 1
            self.a == lo
        """, "unsupported statement Assign")

    def test_G91_assert(self):
        self.reject("assert self.a == 5", "unsupported statement Assert")

    def test_G92_return(self):
        self.reject("""
            self.a == 5
            return
        """, "unsupported statement Return", line=2)
        self.accept(None, lambda t: t.a == 4, src="""
            import vsc.dc as vdc

            @vdc.dataclass
            class T(vdc.RandClass):
                a: vdc.u8 = vdc.rand()
                b: vdc.u8 = vdc.rand()

                @vdc.constraint.value
                def twice(self, v):
                    return v + v

                @vdc.constraint
                def c_probe(self):
                    self.twice(self.a) == 8
        """)

    def test_G93_other_statements(self):
        for body, frag in (("raise ValueError()", "Raise"),
                           ("try:\n    self.a == 1\nexcept Exception:\n    pass",
                            "Try"),
                           ("import os", "Import"),
                           ("del self.a", "Delete"),
                           ("global LIMIT", "Global"),
                           ("def f():\n    pass", "FunctionDef"),
                           ("class K:\n    pass", "ClassDef"),
                           ("async def f():\n    pass", "AsyncFunctionDef")):
            with self.subTest(body=body):
                self.reject(body, frag)
