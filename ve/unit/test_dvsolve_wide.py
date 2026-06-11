"""Phase D — >64-bit (tier-2) field support on the dv-solve back-end.

Fields wider than 64 bits have no path through the 64-bit primary engine, so the
back-end routes them straight to the width-agnostic BV-SAT engine + uniform
sampler (forced on, regardless of the serve-SAT default). These tests exercise
unconstrained, arithmetic, comparison, signed, and mixed wide/narrow RandSets,
asserting the constraints hold and that values actually span the full width.

See doc/notes/dv_solve_phaseD_wide_plan.md.

Skipped automatically when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveWide(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_unconstrained_128_spans_full_width(self):
        """An unconstrained 128-bit field must produce values across its full
        width (phase randomization), not collapse to the low bits or zero."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(128)

        it = W()
        max_bits = 0
        nonzero = 0
        with_high = 0
        for _ in range(40):
            it.randomize()
            v = int(it.a)
            self.assertTrue(0 <= v < (1 << 128))
            nonzero += (v != 0)
            with_high += (v >> 64 != 0)
            max_bits = max(max_bits, v.bit_length())
        self.assertEqual(nonzero, 40, "unconstrained wide field hit 0")
        self.assertGreater(with_high, 0, "no draw used bits above 64")
        self.assertGreater(max_bits, 64, "values never exceeded 64 bits")

    def test_wide_addition(self):
        """c == a + b for 96-bit operands (wraps mod 2^96)."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(96)
                self.b = vsc.rand_bit_t(96)
                self.c = vsc.rand_bit_t(96)

            @vsc.constraint
            def cc(self):
                self.c == self.a + self.b
                self.a > 1000000
                self.b > 1000000

        it = W()
        for _ in range(30):
            it.randomize()
            a, b, c = int(it.a), int(it.b), int(it.c)
            self.assertEqual(c, (a + b) % (1 << 96))
            self.assertGreater(a, 1000000)
            self.assertGreater(b, 1000000)

    def test_wide_comparison(self):
        """x > y for 100-bit operands; values should use the high bits."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(100)
                self.y = vsc.rand_bit_t(100)

            @vsc.constraint
            def cc(self):
                self.x > self.y

        it = W()
        for _ in range(30):
            it.randomize()
            self.assertGreater(int(it.x), int(it.y))

    def test_wide_signed_range(self):
        """A 96-bit signed field constrained to a negative interval — exercises
        sign-extended wide bound/const construction and signed readback."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.s = vsc.rand_int_t(96)

            @vsc.constraint
            def cc(self):
                self.s < -1000
                self.s > -100000000000

        it = W()
        for _ in range(30):
            it.randomize()
            self.assertTrue(-100000000000 < int(it.s) < -1000,
                            "signed wide value out of range: %d" % int(it.s))

    def test_mixed_wide_and_narrow(self):
        """A RandSet mixing a wide field and a <=64-bit field still solves the
        cross constraint correctly."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.w = vsc.rand_bit_t(80)
                self.n = vsc.rand_bit_t(8)

            @vsc.constraint
            def cc(self):
                self.w > self.n
                self.n > 3

        it = W()
        for _ in range(30):
            it.randomize()
            self.assertGreater(int(it.w), int(it.n))
            self.assertGreater(int(it.n), 3)

    def test_wide_inside(self):
        """`inside` with <=64-bit range bounds on a wide field."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(70)

            @vsc.constraint
            def cc(self):
                self.a.inside(vsc.rangelist((100, 200), (5000, 6000)))

        it = W()
        seen = set()
        for _ in range(60):
            it.randomize()
            v = int(it.a)
            self.assertTrue(100 <= v <= 200 or 5000 <= v <= 6000,
                            "value %d outside the membership set" % v)
            seen.add(v)
        self.assertGreater(len(seen), 1, "membership produced a single value")

    def test_width_65_boundary(self):
        """65 bits — the first width past the int64 boundary."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(65)

            @vsc.constraint
            def cc(self):
                self.a > (1 << 63)   # forces bit 63/64 territory

        it = W()
        hit_high = 0
        for _ in range(30):
            it.randomize()
            v = int(it.a)
            self.assertGreater(v, (1 << 63))
            self.assertLess(v, (1 << 65))
            hit_high += (v >> 64 != 0)
        # > 2^63 with 65 bits: roughly half the space has bit 64 set.
        self.assertGreater(hit_high, 0)

    def test_width_255_max(self):
        """255 bits — the hard ceiling (add_var width is a uint8)."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(255)

            @vsc.constraint
            def cc(self):
                self.a > 1000

        it = W()
        for _ in range(20):
            it.randomize()
            v = int(it.a)
            self.assertGreater(v, 1000)
            self.assertLess(v, (1 << 255))

    def test_uint64_high_bit_readback(self):
        """A 64-bit unsigned value with bit 63 set must read back as a large
        positive int, not a negative int64. (dv-solve returns an int64; the
        backend reinterprets unsigned fields by width.)"""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(64)

            @vsc.constraint
            def cc(self):
                self.x == 0xFFFFFFFFFFFFFFFF

        it = W()
        it.randomize()
        self.assertEqual(int(it.x), 0xFFFFFFFFFFFFFFFF)

        @vsc.randobj
        class W2(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(64)

            @vsc.constraint
            def cc(self):
                self.x > (1 << 63)

        it2 = W2()
        for _ in range(20):
            it2.randomize()
            v = int(it2.x)
            self.assertGreaterEqual(v, 0, "unsigned read back negative: %d" % v)
            self.assertGreater(v, (1 << 63))

    def test_wide_equality_literal(self):
        """Equality against a >64-bit literal (lowered to a concat of limbs)."""
        WIDE = 0xDEADBEEFCAFEBABE0123456789ABCDEF

        @vsc.randobj
        class W(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(128)

            @vsc.constraint
            def cc(self):
                self.x == WIDE

        it = W()
        it.randomize()
        self.assertEqual(int(it.x), WIDE)

    def test_wide_unsat_is_failure(self):
        """A jointly-infeasible wide system raises SolveFailure (BV-SAT is the
        authoritative UNSAT verdict for wide problems too)."""
        from vsc.model.solve_failure import SolveFailure

        @vsc.randobj
        class W(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(96)

            @vsc.constraint
            def cc(self):
                self.a > 100
                self.a < 50

        it = W()
        with self.assertRaises(SolveFailure):
            it.randomize()


if __name__ == "__main__":
    unittest.main()
