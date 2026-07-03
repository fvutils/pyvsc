'''
Dataclass-front-end parallel of ve/unit/test_rand_mode.py.

Since dataclass fields are plain values, rand_mode is toggled via the
``set_rand_mode(name, enabled)`` / ``get_rand_mode(name)`` methods rather than the
classic ``it.a.rand_mode = False`` attribute (which required vsc.raw_mode()). Same
behavior: a disabled field holds its value across randomize().

Inline constraints go through the ``as`` proxy (``itc`` below): on the plain
object, ``it.a != x`` would be a no-op Python comparison.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandMode(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_cls(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        # First, test that values vary
        init_a = 0
        init_b = 0
        it = my_cls()

        for i in range(20):
            with it.randomize_with() as itc:
                itc.a != init_a
                itc.b != init_b

            self.assertNotEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a
            init_b = it.b

        # Now, disable rand_mode for a
        it.set_rand_mode("a", False)

        self.assertEqual(it.get_rand_mode("a"), False)
        self.assertEqual(it.get_rand_mode("b"), True)

        for i in range(20):
            with it.randomize_with() as itc:
                itc.b != init_b

            self.assertEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a
            init_b = it.b

        # Now, go back
        it.set_rand_mode("a", True)

        self.assertEqual(it.get_rand_mode("a"), True)
        self.assertEqual(it.get_rand_mode("b"), True)

        for i in range(20):
            with it.randomize_with() as itc:
                itc.a != init_a
                itc.b != init_b

            self.assertNotEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a
            init_b = it.b

    def test_object_level_rand_mode(self):
        # Adapts t_randomize_rand_mode.v: the object-level form
        # ``obj.rand_mode(en)`` toggles every declared-rand field at once. In dc
        # this is ``set_rand_mode(None, en)``.

        @vdc.dataclass
        class Packet(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

        p = Packet()

        # Disable all fields: both hold their pre-set values across randomize.
        p.a = 10
        p.b = 10
        p.set_rand_mode(None, False)
        self.assertEqual(p.get_rand_mode("a"), False)
        self.assertEqual(p.get_rand_mode("b"), False)
        for _ in range(20):
            p.randomize()
            self.assertEqual(p.a, 10)
            self.assertEqual(p.b, 10)

        # Re-enable all fields: both vary again.
        p.set_rand_mode(None, True)
        self.assertEqual(p.get_rand_mode("a"), True)
        self.assertEqual(p.get_rand_mode("b"), True)
        seen = set()
        for _ in range(20):
            with p.randomize_with() as itc:
                itc.a != 10
                itc.b != 10
            self.assertNotEqual(p.a, 10)
            self.assertNotEqual(p.b, 10)
            seen.add((p.a, p.b))
        self.assertGreater(len(seen), 1)

    def test_disabled_field_is_constant_in_constraint(self):
        # Adapts t_randomize_rand_mode_constr.v: a rand_mode(0) field keeps its
        # value AND still participates in constraints as that constant. Disabling
        # ``y`` (=8) leaves ``y > x`` and ``x > 0`` -> x is solved in 1..7.

        @vdc.dataclass
        class Qux(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def x_gt_0(self):
                self.x > 0

            @vdc.constraint
            def y_gt_x(self):
                self.y > self.x

            @vdc.constraint
            def y_lt_10(self):
                self.y < 10

        q = Qux()
        q.y = 8
        q.set_rand_mode("y", False)

        seen_x = set()
        for _ in range(40):
            q.randomize()
            self.assertEqual(q.y, 8)              # held (rand_mode off)
            self.assertGreater(q.x, 0)            # x_gt_0
            self.assertLess(q.x, q.y)             # y_gt_x, with y a constant 8
            seen_x.add(int(q.x))
        # x should spread across its whole feasible window (1..7).
        self.assertEqual(seen_x, set(range(1, 8)))

    def test_nested_subobj_rand_mode(self):
        # Adapts t_randomize_randmode_subobj.v: disabling a field on a nested rand
        # object is honored during the *parent's* randomize. Each sub-object owns
        # its own rand_mode state.

        @vdc.dataclass
        class Inner(vdc.RandClass):
            val1: vdc.u8 = vdc.rand()
            val2: vdc.u8 = vdc.rand()

            @vdc.constraint
            def inner_c(self):
                self.val1 in vdc.rangelist((10, 50))
                self.val2 in vdc.rangelist((60, 100))

        @vdc.dataclass
        class Outer(vdc.RandClass):
            nested: Inner = vdc.rand()
            outer_val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def outer_c(self):
                self.outer_val in vdc.rangelist((1, 20))

        o = Outer()
        # Baseline: everything ranges.
        for _ in range(20):
            o.randomize()
            self.assertTrue(10 <= o.nested.val1 <= 50)
            self.assertTrue(60 <= o.nested.val2 <= 100)
            self.assertTrue(1 <= o.outer_val <= 20)

        # Freeze nested.val1 (out of its own range even) — it must hold, while the
        # rest keep ranging.
        o.nested.val1 = 42
        o.nested.set_rand_mode("val1", False)
        seen2 = set()
        for _ in range(20):
            o.randomize()
            self.assertEqual(o.nested.val1, 42)
            self.assertTrue(60 <= o.nested.val2 <= 100)
            self.assertTrue(1 <= o.outer_val <= 20)
            seen2.add(int(o.nested.val2))
        self.assertGreater(len(seen2), 1)

        # Re-enable: val1 ranges again.
        o.nested.set_rand_mode("val1", True)
        seen1 = set()
        for _ in range(20):
            o.randomize()
            self.assertTrue(10 <= o.nested.val1 <= 50)
            seen1.add(int(o.nested.val1))
        self.assertGreater(len(seen1), 1)

    def test_disabled_field_unsat(self):
        # Adapts t_rand_member_mode_deriv.v: a disabled field still participates
        # in constraints as a constant, so if its fixed value violates a
        # constraint the randomize is UNSAT (it cannot move the field to comply).

        @vdc.dataclass
        class RandomValue(vdc.RandClass):
            value: vdc.u8 = vdc.rand()

            @vdc.constraint
            def small(self):
                self.value < 10

        rv = RandomValue()
        rv.value = 11                    # violates value < 10
        rv.set_rand_mode("value", False)
        try:
            rv.randomize()
            self.fail("Expected a solve failure (disabled value=11 breaks value<10)")
        except vdc.SolveFailure:
            pass
        # The field is untouched by the failed solve.
        self.assertEqual(rv.value, 11)

        # With a consistent held value the same solve succeeds and holds it.
        rv.value = 5
        rv.randomize()
        self.assertEqual(rv.value, 5)
