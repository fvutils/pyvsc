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
