"""V20 (fallback_elimination_v2_plan.md, R14) — a mixed-sign comparison at
64 bits is served by dv-solve, not deferred.

SV makes a mixed-sign expression unsigned: the signed operand is read as its
bit pattern. The translator zero-extends it one bit wider into an aux so the
engine compares values; at 64 bits that needs 65, past the primary engine,
so the RandSet deferred (``translator-unsupported``). Now the 65-bit extend is
emitted as is and the RandSet is served by BV-SAT, which is width-agnostic.
Each test checks every draw against SV semantics, in strict mode.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase

M64 = (1 << 64) - 1


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


def _mk(op):
    @vsc.randobj
    class C(object):
        def __init__(s):
            s.a = vsc.rand_int64_t()
            s.b = vsc.rand_uint64_t()

        @vsc.constraint
        def c(s):
            if op == "lt":
                s.a < s.b
            elif op == "lt_neg":
                s.a < s.b
                s.a < 0
            elif op == "ge_small":
                s.a >= s.b
                s.b < 100
            elif op == "eq_upper":
                s.a == s.b
                s.b > (1 << 63)
    return C()


def _holds(op, a, b):
    ua = a & M64                      # the signed operand's unsigned pattern
    return {"lt": ua < b,
            "lt_neg": ua < b and a < 0,
            "ge_small": ua >= b and b < 100,
            "eq_upper": ua == b and b > (1 << 63)}[op]


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveMixedSign64(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _run(self, op, n):
        obj = _mk(op)
        negs = 0
        with _strict_no_fallback():
            for _ in range(n):
                obj.randomize()
                a, b = int(obj.a), int(obj.b)
                self.assertTrue(_holds(op, a, b), "%s: a=%d b=%d" % (op, a, b))
                negs += a < 0
        return negs / n

    def test_lt(self):
        """The probe shape (`mixed_sign_64`). Uniform over the solutions, a
        is negative (pattern >= 2^63) in 1/4 of them."""
        p = self._run("lt", 300)
        self.assertTrue(0.15 < p < 0.35, p)

    def test_lt_negative_signed(self):
        self.assertEqual(self._run("lt_neg", 100), 1.0)

    def test_ge_small_unsigned(self):
        """`a >= b` with small b: a negative a (huge pattern) qualifies."""
        p = self._run("ge_small", 200)
        self.assertTrue(0.3 < p < 0.7, p)

    def test_eq_upper_half(self):
        """Equal patterns above 2^63: a is negative every time."""
        self.assertEqual(self._run("eq_upper", 100), 1.0)


if __name__ == "__main__":
    unittest.main()
