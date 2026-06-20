'''
Generic constraints (PSS 3.1 §13.1.1) in the vdc dataclass front-end — M1.

Pins: a ``@vdc.constraint.generic`` block applies only when referenced (by name)
from a fixed constraint — as a statement (whole body spliced in) or as a boolean
term (``a() | b()``, solver-chosen with lookahead). Plus the decoration-time
reference-validation errors. Mirrors classic ``ve/unit/test_constraint_dynamic.py``.

Note on distribution: ``small() | jumbo()`` is a plain disjunction, so the solver
returns *any* satisfying value — it does not promise a fair split between the two
windows (the wider window dominates). Tests therefore assert *soundness* (the value
always lands in one window) and exercise each branch via single references, rather
than asserting a branch distribution the OR does not guarantee.

See doc/notes/dc_generic_constraints_{design,impl_plan}.md.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestGenericConstraint(DcTestCase):

    def test_example_136_boolean_ref(self):
        # PSS Example 136: pkt_sz in [1..100] (small) OR [1501..] (jumbo).
        @vdc.dataclass
        class send_pkt(vdc.RandClass):
            pkt_sz: vdc.u16 = vdc.rand()

            @vdc.constraint
            def pkt_sz_c(self):
                self.pkt_sz > 0

            @vdc.constraint.generic
            def small_pkt_c(self):
                self.pkt_sz <= 100

            @vdc.constraint.generic
            def jumbo_pkt_c(self):
                self.pkt_sz > 1500

            @vdc.constraint
            def interesting_sz_c(self):
                self.small_pkt_c() | self.jumbo_pkt_c()

        it = send_pkt()
        for _ in range(200):
            it.randomize()
            self.assertTrue(1 <= it.pkt_sz <= 100 or it.pkt_sz > 1500,
                            "pkt_sz=%d out of either window" % it.pkt_sz)

    def test_boolean_ref_single_generic(self):
        # Referencing one generic as a boolean term applies its body.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint.generic
            def a_small(self):
                self.a < 10

            @vdc.constraint
            def use(self):
                self.a_small()

        it = my_c()
        for _ in range(100):
            it.randomize()
            self.assertLess(it.a, 10)

    def test_unreferenced_generic_does_not_apply(self):
        # A generic that is never referenced must NOT constrain the field.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint.generic
            def a_small(self):
                self.a < 10

        it = my_c()
        saw_big = False
        for _ in range(200):
            it.randomize()
            saw_big |= it.a >= 10
        self.assertTrue(saw_big, "unreferenced generic still constrained the field")

    def test_statement_ref_applies_whole_body(self):
        # A generic referenced as a bare statement applies its full multi-item body.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint.generic
            def both(self):
                self.a < 20
                self.b > 200

            @vdc.constraint
            def use(self):
                self.both()

        it = my_c()
        for _ in range(100):
            it.randomize()
            self.assertLess(it.a, 20)
            self.assertGreater(it.b, 200)

    def test_generic_references_generic(self):
        # A generic may reference another generic (transitive application).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint.generic
            def inner(self):
                self.a < 5

            @vdc.constraint.generic
            def outer(self):
                self.inner()

            @vdc.constraint
            def use(self):
                self.outer()

        it = my_c()
        for _ in range(100):
            it.randomize()
            self.assertLess(it.a, 5)


class TestGenericConstraintParams(DcTestCase):

    def test_keyword_and_default_actuals(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u16 = vdc.rand()

            @vdc.constraint
            def in_window(self, lo, hi=110):
                self.x >= lo
                self.x <= hi

            @vdc.constraint
            def pick(self):
                # keyword actual + an omitted default (hi defaults to 110)
                self.in_window(10, hi=20) | self.in_window(lo=100)

        it = my_c()
        for _ in range(200):
            it.randomize()
            self.assertTrue(10 <= it.x <= 20 or 100 <= it.x <= 110,
                            "x=%d outside either window" % it.x)

    def test_rand_field_actual(self):
        # An actual may be another rand field (relation template).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            n: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ge(self, v):
                self.x >= v

            @vdc.constraint
            def use(self):
                self.n > 10
                self.ge(self.n)        # x >= n, n random

        it = my_c()
        for _ in range(100):
            it.randomize()
            self.assertGreaterEqual(it.x, it.n)
            self.assertGreater(it.n, 10)

    def test_value_generic_dual_use_readback(self):
        # A value generic is also a plain method: post-solve it computes against
        # the concrete field values (design §7.8).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            sz: vdc.u16 = vdc.rand()

            @vdc.constraint
            def aligned(self, n):
                return (self.sz // n) * n

            @vdc.constraint
            def c(self):
                self.sz == self.aligned(8)
                self.sz > 0

        it = my_c()
        for _ in range(50):
            it.randomize()
            self.assertEqual(it.sz % 8, 0)
            self.assertEqual(it.sz, it.aligned(8))   # readback matches solve

    def test_wrong_keyword_is_error(self):
        with self.assertRaises(TypeError) as cm:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                x: vdc.u8 = vdc.rand()

                @vdc.constraint
                def w(self, lo, hi):
                    self.x >= lo

                @vdc.constraint
                def use(self):
                    self.w(1, bogus=2)
        self.assertIn("keyword", str(cm.exception).lower())


class TestGenericConstraintKindChange(DcTestCase):

    def test_kind_change_override_warns(self):
        @vdc.dataclass
        class Base(vdc.RandClass):
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def k(self):
                self.y < 10

        with self.assertWarns(UserWarning):
            @vdc.dataclass
            class Sub(Base):
                @vdc.constraint.generic
                def k(self):           # fixed -> generic: changes always-on-ness
                    self.y > 200


class TestGenericConstraintInline(DcTestCase):
    # Inline (randomize_with) references — parity with classic
    # ve/unit/test_constraint_dynamic.py.

    def _mk(self):
        @vdc.dataclass
        class my_cls(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def a_c(self):
                self.a <= 100

            @vdc.constraint.generic
            def a_small(self):
                self.a.inside(vdc.rangelist(vdc.rng(1, 10)))

            @vdc.constraint.generic
            def a_large(self):
                self.a.inside(vdc.rangelist(vdc.rng(90, 100)))
        return my_cls()

    def test_inline_single_ref(self):
        it = self._mk()
        for _ in range(20):
            with it.randomize_with() as h:
                h.a_small()
            self.assertTrue(1 <= it.a <= 10, "a=%d not in 1..10" % it.a)
            with it.randomize_with() as h:
                h.a_large()
            self.assertTrue(90 <= it.a <= 100, "a=%d not in 90..100" % it.a)

    def test_inline_or_ref(self):
        it = self._mk()
        for _ in range(40):
            with it.randomize_with() as h:
                h.a_small() | h.a_large()
            self.assertTrue(1 <= it.a <= 10 or 90 <= it.a <= 100,
                            "a=%d not in either window" % it.a)

    def test_inline_parameterized_ref(self):
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u16 = vdc.rand()

            @vdc.constraint
            def base(self):
                self.x < 1000

            @vdc.constraint
            def window(self, lo, hi):
                self.x >= lo
                self.x <= hi

        it = my_c()
        for _ in range(30):
            with it.randomize_with() as h:
                h.window(100, 110) | h.window(500, 510)
            self.assertTrue(100 <= it.x <= 110 or 500 <= it.x <= 510,
                            "x=%d outside either window" % it.x)

    def test_inline_field_actual_is_error(self):
        # A field-valued actual to an inline parameterized ref is rejected (clearly).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ge(self, v):
                self.x >= v

        it = my_c()
        with self.assertRaises(TypeError):
            with it.randomize_with() as h:
                h.ge(h.x)

    def test_inline_unreferenced_full_range(self):
        # Without referencing a generic, a spans the fixed range 0..100.
        it = self._mk()
        saw_mid = False
        for _ in range(60):
            it.randomize()
            saw_mid |= 11 <= it.a <= 89
        self.assertTrue(saw_mid, "generics applied without being referenced")


class TestGenericConstraintErrors(DcTestCase):
    # All of these must fail at *decoration time* (class definition), not at solve.

    def test_reference_fixed_is_error(self):
        with self.assertRaises(TypeError) as cm:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def fixed_one(self):
                    self.a < 10

                @vdc.constraint
                def use(self):
                    self.fixed_one()      # referencing a FIXED constraint
        self.assertIn("fixed", str(cm.exception).lower())

    def test_reference_unknown_is_error(self):
        with self.assertRaises(TypeError) as cm:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def use(self):
                    self.nonexistent()
        self.assertIn("unknown", str(cm.exception).lower())

    def test_reference_cycle_is_error(self):
        with self.assertRaises(TypeError) as cm:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint.generic
                def g1(self):
                    self.g2()

                @vdc.constraint.generic
                def g2(self):
                    self.g1()

                @vdc.constraint
                def use(self):
                    self.g1()
        self.assertIn("cyclic", str(cm.exception).lower())

    def test_boolean_of_nonboolean_body_is_error(self):
        # A generic whose body has a soft item cannot be used as a boolean term.
        with self.assertRaises(TypeError) as cm:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint.generic
                def has_soft(self):
                    self.a < 100
                    vdc.soft(self.a == 50)

                @vdc.constraint
                def use(self):
                    self.has_soft() | (self.a > 200)
        self.assertIn("boolean", str(cm.exception).lower())
