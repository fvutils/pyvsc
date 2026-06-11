'''
Phase-1 solver conformance harness (plan P1-T1..T6, design §9).

Randomizes a corpus of @randobj classes under each available back-end and
asserts *constraint satisfaction* (not equal values, since random stability is
per-engine). dv-solve cases are skipped automatically when the native library
is not present, so this file is green in a Boolector-only environment and
exercises both engines in the CI matrix job that builds libdv_solve.so.

@author: solver-backend integration
'''
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _backend_available(name):
    try:
        select_backend(name)
        return True
    except Exception:
        return False


BACKENDS = [b for b in ("boolector", "dv-solve") if _backend_available(b)]


class SolverConformanceBase(VscTestCase):
    """Helpers shared by the conformance cases."""

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _each_backend(self):
        return BACKENDS

    def randomize_check(self, cls, check, n=25, seed=0, backends=None):
        """Randomize ``cls`` ``n`` times under each back-end and assert
        ``check(obj)`` holds every time."""
        for backend in (backends or self._each_backend()):
            random.seed(seed)
            ctor.set_solver_backend(backend)
            obj = cls()
            for it in range(n):
                obj.randomize()
                self.assertTrue(
                    check(obj),
                    "[%s] iter %d: constraint violated (state=%s)" % (
                        backend, it, _dump(obj)))


def _dump(obj):
    out = {}
    for k, v in vars(obj).items():
        try:
            out[k] = int(v)
        except Exception:
            pass
    return out


class TestConformanceCore(SolverConformanceBase):
    """P1-T1: common constraint subset, satisfaction under both back-ends."""

    def test_single_var_range(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a >= 10
                self.a <= 20
        self.randomize_check(C, lambda o: 10 <= int(o.a) <= 20)

    def test_relational(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < self.b
                self.b < 100
        self.randomize_check(C, lambda o: int(o.a) < int(o.b) < 100)

    def test_arithmetic(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.s = vsc.rand_uint16_t()
                self.d = vsc.rand_uint16_t()
            @vsc.constraint
            def c(self):
                self.a > 0
                self.b > 0
                self.s == self.a + self.b
                self.d == self.a * self.b
        self.randomize_check(
            C, lambda o: int(o.s) == int(o.a) + int(o.b)
                         and int(o.d) == int(o.a) * int(o.b))

    def test_bitwise(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                (self.a & 0x0f) == 0     # low nibble clear
                (self.a | 0x80) == self.a  # high bit set
        self.randomize_check(
            C, lambda o: (int(o.a) & 0x0f) == 0 and (int(o.a) & 0x80) != 0)

    def test_unique(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.d = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < 5
                self.b < 5
                self.d < 5
                vsc.unique(self.a, self.b, self.d)
        self.randomize_check(
            C, lambda o: len({int(o.a), int(o.b), int(o.d)}) == 3)

    def test_inside_multirange(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a.inside(vsc.rangelist(vsc.rng(10, 20), vsc.rng(40, 50)))
        self.randomize_check(
            C, lambda o: 10 <= int(o.a) <= 20 or 40 <= int(o.a) <= 50)

    def test_if_else(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < 50
                with vsc.if_then(self.a < 10):
                    self.b == 1
                with vsc.else_then:
                    self.b == 2
        self.randomize_check(
            C, lambda o: int(o.b) == (1 if int(o.a) < 10 else 2))

    def test_implies(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < 50
                with vsc.implies(self.a < 10):
                    self.b > 100
        self.randomize_check(
            C, lambda o: (int(o.b) > 100) if int(o.a) < 10 else True)


class TestConformanceSignedWidth(SolverConformanceBase):
    """P1-T5: signed/unsigned and mixed-width matrix."""

    def test_signed_negative(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_int8_t()
            @vsc.constraint
            def c(self):
                self.a > -50
                self.a < -10
        self.randomize_check(C, lambda o: -50 < int(o.a) < -10)

    def test_signed_relational(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_int8_t()
                self.b = vsc.rand_int8_t()
            @vsc.constraint
            def c(self):
                self.a < 0
                self.b > 0
                self.a < self.b
        self.randomize_check(C, lambda o: int(o.a) < 0 < int(o.b) and int(o.a) < int(o.b))

    def test_mixed_width_arith(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()    # 8
                self.b = vsc.rand_uint16_t()   # 16
                self.s = vsc.rand_uint32_t()   # 32
            @vsc.constraint
            def c(self):
                self.a > 100
                self.b > 1000
                self.s == self.a + self.b
        self.randomize_check(
            C, lambda o: int(o.s) == int(o.a) + int(o.b)
                         and int(o.a) > 100 and int(o.b) > 1000)

    def test_width_boundaries(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_int16_t()
            @vsc.constraint
            def c(self):
                self.a.inside(vsc.rangelist(0, 255))      # full unsigned range
                self.b.inside(vsc.rangelist(-32768, 32767))  # full signed range
        self.randomize_check(
            C, lambda o: int(o.a) in (0, 255) and int(o.b) in (-32768, 32767))


class TestConformanceSoft(SolverConformanceBase):
    """P1-T4: soft constraints resolve consistently across back-ends."""

    def _winner(self, backend, seed=0):
        random.seed(seed)
        ctor.set_solver_backend(backend)

        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < 10
                vsc.soft(self.a == 1)   # declared first -> preferred
                vsc.soft(self.a == 2)   # conflicts with the first
        obj = C()
        obj.randomize()
        return int(obj.a)

    def test_soft_no_conflict(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a < 10
                vsc.soft(self.a == 7)
        self.randomize_check(C, lambda o: int(o.a) == 7)

    def test_soft_conflict_same_winner(self):
        # Two soft constraints conflict; both back-ends must relax the same one
        # and therefore agree on the resulting value (per-engine value streams
        # may differ in general, but the soft *outcome* must match).
        if len(self._each_backend()) < 2:
            self.skipTest("needs both back-ends to compare soft resolution")
        results = {b: self._winner(b) for b in self._each_backend()}
        self.assertEqual(
            len(set(results.values())), 1,
            "back-ends disagree on soft resolution: %s" % results)


class TestConformanceDeterminism(SolverConformanceBase):
    """P1-T3: same seed -> identical value stream within an engine."""

    def _stream(self, backend, seed):
        random.seed(seed)
        ctor.set_solver_backend(backend)

        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint32_t()
            @vsc.constraint
            def c(self):
                self.a < self.b
        obj = C()
        out = []
        for _ in range(8):
            obj.randomize()
            out.append((int(obj.a), int(obj.b)))
        return out

    def test_determinism(self):
        for backend in self._each_backend():
            self.assertEqual(self._stream(backend, 5), self._stream(backend, 5),
                             "[%s] same seed not reproducible" % backend)

    def test_seed_sensitivity(self):
        for backend in self._each_backend():
            self.assertNotEqual(self._stream(backend, 1), self._stream(backend, 2),
                                "[%s] different seeds gave identical streams" % backend)


class TestConformanceDistribution(SolverConformanceBase):
    """P1-T2: an unconstrained-ish field covers its domain under dv-solve."""

    def test_domain_coverage(self):
        for backend in self._each_backend():
            random.seed(0)
            ctor.set_solver_backend(backend)

            @vsc.randobj
            class C(object):
                def __init__(self):
                    self.a = vsc.rand_uint8_t()
                @vsc.constraint
                def c(self):
                    self.a < 16   # 16 buckets
            obj = C()
            seen = set()
            for _ in range(400):
                obj.randomize()
                seen.add(int(obj.a))
            # Every value in [0,16) should appear with high probability.
            self.assertGreaterEqual(
                len(seen), 14,
                "[%s] poor spread: only %d/16 values hit" % (backend, len(seen)))


class TestConformanceUnsat(SolverConformanceBase):
    """P1-T6: over-constrained object raises SolveFailure under each back-end."""

    def test_unsat(self):
        from vsc.model.solve_failure import SolveFailure
        for backend in self._each_backend():
            ctor.set_solver_backend(backend)

            @vsc.randobj
            class C(object):
                def __init__(self):
                    self.a = vsc.rand_uint8_t()
                @vsc.constraint
                def c(self):
                    self.a < 5
                    self.a > 10
            with self.assertRaises(SolveFailure, msg="[%s]" % backend):
                C().randomize()


class TestArithmeticWrap(SolverConformanceBase):
    """Bit-accurate fixed-width 2's-complement arithmetic: an operation whose
    true result overflows the result width must wrap (mod 2^w), matching
    SystemVerilog / Boolector. dv-solve gained modular var-var add/sub/mul/shl
    propagators; these assert the wrapped result under every available back-end
    (and that the two agree)."""

    def _check_all(self, cls, expected):
        for backend in self._each_backend():
            random.seed(0)
            ctor.set_solver_backend(backend)
            obj = cls()
            obj.randomize()
            self.assertEqual(
                int(obj.r), expected,
                "[%s] expected wrapped result %d, got %d" % (backend, expected, int(obj.r)))

    def test_add_overflow_wraps(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t(); self.b = vsc.rand_uint8_t(); self.r = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a == 200; self.b == 100; self.r == self.a + self.b
        self._check_all(C, (200 + 100) & 0xff)   # 44

    def test_sub_underflow_wraps(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t(); self.b = vsc.rand_uint8_t(); self.r = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a == 10; self.b == 20; self.r == self.a - self.b
        self._check_all(C, (10 - 20) & 0xff)     # 246

    def test_mul_overflow_wraps(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t(); self.b = vsc.rand_uint8_t(); self.r = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a == 20; self.b == 20; self.r == self.a * self.b
        self._check_all(C, (20 * 20) & 0xff)     # 144

    def test_shl_drops_high_bits(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t(); self.b = vsc.rand_uint8_t(); self.r = vsc.rand_uint8_t()
            @vsc.constraint
            def c(self):
                self.a == 1; self.b == 10; self.r == self.a << self.b
        self._check_all(C, (1 << 10) & 0xff)     # 0

    def test_signed_add_wraps(self):
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_int8_t(); self.b = vsc.rand_int8_t(); self.r = vsc.rand_int8_t()
            @vsc.constraint
            def c(self):
                self.a == 100; self.b == 50; self.r == self.a + self.b
        self._check_all(C, ((100 + 50 + 128) % 256) - 128)   # -106

    def test_no_overflow_exact(self):
        # Sanity: when no overflow occurs, the result is exact (fast path).
        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_uint16_t(); self.b = vsc.rand_uint16_t(); self.r = vsc.rand_uint16_t()
            @vsc.constraint
            def c(self):
                self.a == 300; self.b == 400; self.r == self.a + self.b
        self._check_all(C, 700)


class TestSignedDivMod(SolverConformanceBase):
    """Signed ``/`` and ``%`` follow SystemVerilog truncated semantics
    (division truncates toward zero; remainder takes the sign of the dividend)
    under every back-end, including negative divisors."""

    @staticmethod
    def _sv_div(a, b):
        return 0 if b == 0 else (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)

    @staticmethod
    def _sv_mod(a, b):
        return 0 if b == 0 else (abs(a) % abs(b)) * (-1 if a < 0 else 1)

    def _solve(self, backend, a_val, b_val):
        random.seed(0)
        ctor.set_solver_backend(backend)

        @vsc.randobj
        class C(object):
            def __init__(self):
                self.a = vsc.rand_int8_t(); self.b = vsc.rand_int8_t()
                self.q = vsc.rand_int8_t(); self.r = vsc.rand_int8_t()
            @vsc.constraint
            def c(self):
                self.a == a_val; self.b == b_val
                self.q == self.a / self.b
                self.r == self.a % self.b
        obj = C()
        obj.randomize()
        return int(obj.q), int(obj.r)

    def test_sv_semantics_all_sign_combos(self):
        cases = [(-7, 3), (7, -3), (-7, -3), (-7, 2), (7, 3),
                 (-8, 3), (5, -2), (-1, 4), (-100, 7), (100, -7)]
        for backend in self._each_backend():
            for a, b in cases:
                q, r = self._solve(backend, a, b)
                self.assertEqual(
                    (q, r), (self._sv_div(a, b), self._sv_mod(a, b)),
                    "[%s] %d / %% %d -> (%d,%d), expected SV (%d,%d)" % (
                        backend, a, b, q, r, self._sv_div(a, b), self._sv_mod(a, b)))


if __name__ == "__main__":
    unittest.main()
