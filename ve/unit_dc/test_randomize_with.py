'''
Dataclass-front-end parallel of ve/unit/test_randomize_with.py.

P1 subset: test_smoke. The classic test_randomize_with_randselect uses standalone
field randomization (vsc.randomize_with(self.value)) + randselect, which lands later.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class _Arrs(vdc.RandClass):
    i: vdc.u8 = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(size=5)
    ra: list[vdc.u8] = vdc.rand(max_size=6)

    @vdc.constraint
    def c(self):
        self.ra.size <= 6


class TestRandomizeWith(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_class(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u16 = vdc.rand()
            c: vdc.u16 = vdc.rand()
            d: vdc.u16 = vdc.rand()

            @vdc.constraint
            def my_a_c(self):
                self.a < 10
                with vdc.if_then(self.a == 2):
                    self.b < 1000
                with vdc.else_then():
                    self.b < 2000

        c = my_class()

        for i in range(1000):
            with c.randomize_with() as it:
                it.a == (i % 10)
            self.assertEqual(it.a, (i % 10))

    def test_array_element(self):
        # B13: it.arr[k] was a bit-select of the array (AttributeError at
        # randomize). Constant and symbolic indices, and a random-size array.
        o = _Arrs()
        for _ in range(20):
            with o.randomize_with() as it:
                it.arr[3] == 77
                it.i < 5
                it.arr[it.i] == 9
                it.ra.size == 4
                it.ra[1] == 3
            self.assertEqual(o.arr[3], 77)
            self.assertEqual(o.arr[o.i], 9)
            self.assertEqual(len(o.ra), 4)
            self.assertEqual(o.ra[1], 3)
        # The object still randomizes on its own afterwards.
        for _ in range(5):
            o.randomize()
            self.assertLessEqual(len(o.ra), 6)

    def test_array_sum(self):
        o = _Arrs()
        for _ in range(10):
            with o.randomize_with() as it:
                it.arr.sum == 100
            self.assertEqual(sum(o.arr), 100)

    def test_array_foreach(self):
        # vdc.foreach over it.arr takes the whole array.
        o = _Arrs()
        for _ in range(20):
            with o.randomize_with() as it:
                with vdc.foreach(it.arr, idx=True) as i:
                    it.arr[i] == i + 3
            self.assertEqual(list(o.arr), [3, 4, 5, 6, 7])


class TestLegacyInline(DcTestCase):
    """The operator path, used when a body cannot be parsed."""

    def setUp(self):
        super().setUp()
        from vsc.dc import inline
        saved = inline._INLINE_PARSE
        inline._INLINE_PARSE = False
        self.addCleanup(setattr, inline, "_INLINE_PARSE", saved)

    def test_loop_over_array_is_an_error(self):
        # Iterating it.arr is an error, not a loop that never ends (Python
        # iterates through __getitem__).
        o = _Arrs()
        with self.assertRaisesRegex(TypeError, "needs the body parsed"):
            with o.randomize_with() as it:
                for x in it.arr:
                    x < 5

    def test_truth_test_is_an_error(self):
        # 'and', 'or', 'not' and 'if' test an expression for truth, which
        # silently loses a constraint on this path (plan 3.8).
        import vsc.types
        o = _Arrs()
        for name, body in (
                ("and", lambda it: it.i > 3 and it.i < 6),
                ("or", lambda it: it.i < 3 or it.i > 6),
                ("not", lambda it: not (it.i == 5)),
                ("if", lambda it: 1 if it.i > 3 else 0)):
            with self.subTest(op=name):
                with self.assertRaisesRegex(TypeError, "tested for truth"):
                    with o.randomize_with() as it:
                        body(it)
                self.assertIsNone(vsc.types.truth_hook)
        # '&' and 'in' a rangelist still work.
        for _ in range(10):
            with o.randomize_with() as it:
                (it.i > 3) & (it.i < 6)
                it.arr[0] in vdc.rangelist(7, 9)
            self.assertTrue(3 < o.i < 6)
            self.assertIn(o.arr[0], (7, 9))

    def test_body_without_source(self):
        # exec'd code has no source to parse, so it runs on this path even
        # with parsing on; a truth test there is reported, not ignored.
        from vsc.dc import inline
        inline._INLINE_PARSE = True
        o = _Arrs()
        ns = {"o": o}
        exec("with o.randomize_with() as it:\n"
             "    it.i == 4\n", ns)
        self.assertEqual(o.i, 4)
        with self.assertRaisesRegex(TypeError, "tested for truth"):
            exec("with o.randomize_with() as it:\n"
                 "    it.i > 3 and it.i < 6\n", ns)
