"""V16 (fallback_elimination_v2_plan.md, wide plan W1) — fields wider than
255 bits are served by dv-solve, not deferred.

The back-end used to defer any RandSet with a field over 255 bits
(``reason_code="width"``), on the grounds that ``add_var`` carried width as a
uint8. The API has carried uint16 widths since, and BV-SAT is width-agnostic,
so the cap is now the encodable maximum (65535). Each test runs in strict mode
(no fallback), so a deferral fails the test rather than reaching Boolector.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend, BackendIncomplete
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _strict_no_fallback():
    saved = rnd._NO_FALLBACK
    rnd._NO_FALLBACK = True
    try:
        yield
    finally:
        rnd._NO_FALLBACK = saved


def _mk(W, shape):
    @vsc.randobj
    class C(object):
        def __init__(self):
            self.a = vsc.rand_bit_t(W)
            self.b = vsc.rand_bit_t(W)

        @vsc.constraint
        def cc(self):
            if shape == "slice":
                self.a[15:0] == 0x1234
                self.a[W - 1:W - 8] == 0xA5
            elif shape == "inside":
                self.a.inside(vsc.rangelist(
                    [(1 << (W - 2)), (1 << (W - 2)) + 999], 7))
            elif shape == "lt":
                self.a < self.b
                self.b < (1 << (W - 1))
            elif shape == "add":
                self.a + self.b == (1 << (W - 1)) + 12345
    return C()


def _check(W, shape, a, b):
    if shape == "slice":
        return (a & 0xFFFF) == 0x1234 and (a >> (W - 8)) == 0xA5
    if shape == "inside":
        lo = 1 << (W - 2)
        return a == 7 or lo <= a <= lo + 999
    if shape == "lt":
        return a < b < (1 << (W - 1))
    if shape == "add":
        return a + b == (1 << (W - 1)) + 12345
    raise AssertionError(shape)


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveWidthGuard(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _run(self, W, shape, n):
        obj = _mk(W, shape)
        seen = set()
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                a, b = int(obj.a), int(obj.b)
                self.assertTrue(0 <= a < (1 << W) and 0 <= b < (1 << W))
                self.assertTrue(_check(W, shape, a, b),
                                "%s W=%d violated: a=%#x b=%#x" % (shape, W, a, b))
                seen.add(a)
        if shape != "inside" or n > 4:
            self.assertGreater(len(seen), 1, "%s W=%d: no variety" % (shape, W))

    def test_256(self):
        for shape in ("slice", "inside", "lt", "add"):
            with self.subTest(shape=shape):
                self._run(256, shape, 10)

    def test_1024(self):
        for shape in ("slice", "inside", "lt"):
            with self.subTest(shape=shape):
                self._run(1024, shape, 10)
        # `+` re-blasts per sampler level (~0.8 s/draw at 1024 bits; W5/V19).
        self._run(1024, "add", 2)

    def test_4096(self):
        for shape in ("slice", "inside", "lt"):
            with self.subTest(shape=shape):
                self._run(4096, shape, 4)

    def test_wide_signed_readback(self):
        """A negative value of a 300-bit signed field reads back as a
        negative Python int, at full width."""
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_int_t(300)

            @vsc.constraint
            def cc(self):
                self.a < -(1 << 200)
                self.a > -(1 << 200) - 1000

        obj = C()
        with _strict_no_fallback():
            for _ in range(10):
                obj.randomize()
                v = int(obj.a)
                self.assertTrue(-(1 << 200) - 1000 < v < -(1 << 200), hex(v))

    def test_constant_at_the_width_cap(self):
        """`b < 2^(W-1)` at W = 65534: 2^65533 is a 65535-bit signed literal.
        Its concat chain had an unsized, so 64-bit, top limb and came to 65536
        bits, over the cap; it is now one exact-width native constant node
        (v2 plan V17)."""
        self._run(65534, "lt", 2)

    def test_constant_over_max_defers(self):
        """2^65534 is a 65536-bit signed literal, over the 65535-bit cap:
        the RandSet defers with the `width` reason until V26 raises it."""
        obj = _mk(65535, "lt")
        with _strict_no_fallback():
            with self.assertRaises(Exception) as cm:
                obj.randomize()
        self.assertIn("width", str(cm.exception))
        self.assertIn("constant", str(cm.exception))

    def test_over_max_still_defers(self):
        """Above the encodable maximum the RandSet still defers with the
        `width` reason (V26 raises the maximum to 2^32-1)."""
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(dvb._MAX_FIELD_WIDTH + 1)
                self.b = vsc.rand_bit_t(dvb._MAX_FIELD_WIDTH + 1)

            @vsc.constraint
            def cc(self):
                self.a != self.b

        obj = C()
        with _strict_no_fallback():
            with self.assertRaises(Exception) as cm:
                obj.randomize()
        self.assertIn("width", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
