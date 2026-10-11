"""dv-solve gate: randomization is uniform over solutions under a relation.

IEEE 1800 asks for a uniform distribution over the legal value combinations,
and that is what external evaluations measure (SyoSil's whitepaper, §3.4.2:
`x <= y`, both in [0:9], 10,000 draws, each of the 55 legal cells checked).
Drawing one field at a time, each uniformly from what the previous draws
leave, is not that: the grid's corner cells came out at 5.5% instead of 1.8%.
See doc/notes/dist_relational_grid_findings.md.

Skipped when dv-solve is absent.
"""
import random
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


@vsc.randobj
class Grid(object):
    def __init__(self):
        self.x = vsc.rand_uint8_t()
        self.y = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        self.x < 10
        self.y < 10
        self.x <= self.y


@vsc.randobj
class Lt(object):
    def __init__(self):
        self.a = vsc.rand_uint8_t()
        self.b = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        self.a < self.b


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveUniformSolutions(VscTestCase):

    def setUp(self):
        super().setUp()
        random.seed(1)
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_syosil_grid(self):
        n = 10000
        g = Grid()
        counts = {}
        for _ in range(n):
            g.randomize()
            cell = (int(g.x), int(g.y))
            self.assertLessEqual(cell[0], cell[1])
            counts[cell] = counts.get(cell, 0) + 1
        cells = [(x, y) for x in range(10) for y in range(10) if x <= y]
        exp = n / len(cells)
        chi2 = sum((counts.get(c, 0) - exp) ** 2 / exp for c in cells)
        # 54 degrees of freedom: p = 1e-4 at about 99. The one-at-a-time draw
        # scored ~2000; constrainedrandom's rejection sampling ~55.
        self.assertLess(chi2, 99, "grid chi2 %.0f (54 dof)" % chi2)

    def test_a_lt_b_mean(self):
        n = 8000
        o = Lt()
        total = 0
        for _ in range(n):
            o.randomize()
            total += int(o.a)
        # Uniform over solutions: P(a=k) ∝ 255-k, mean 85. One at a time: ~95.
        self.assertAlmostEqual(total / n, 85.0, delta=3.0)

    def test_control_independent_fields_stay_uniform(self):
        @vsc.randobj
        class Free(object):
            def __init__(self):
                self.x = vsc.rand_uint8_t()
                self.y = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                self.x < 10
                self.y < 10
        n = 10000
        o = Free()
        counts = {}
        for _ in range(n):
            o.randomize()
            cell = (int(o.x), int(o.y))
            counts[cell] = counts.get(cell, 0) + 1
        exp = n / 100
        chi2 = sum((counts.get((x, y), 0) - exp) ** 2 / exp
                   for x in range(10) for y in range(10))
        self.assertLess(chi2, 160, "chi2 %.0f (99 dof)" % chi2)


@vsc.randobj
class SImpliesD(object):
    """IEEE 1800's variable-ordering example: s -> d == 0."""
    def __init__(self, ordered):
        self.ordered = ordered
        self.s = vsc.rand_bit_t(1)
        self.d = vsc.rand_uint32_t()

    @vsc.constraint
    def c(self):
        if self.ordered:
            vsc.solve_order(self.s, self.d)
        with vsc.implies(self.s == 1):
            self.d == 0


@vsc.randobj
class WideBeforeNarrow(object):
    """a (8 bits) before b (1 bit), a != 0 -> b == 0. Smallest-domain-first
    decides b first, and b == 1 forces a == 0 half the time; the order makes
    a uniform over its 256 values."""
    def __init__(self):
        self.a = vsc.rand_uint8_t()
        self.b = vsc.rand_bit_t(1)

    @vsc.constraint
    def c(self):
        vsc.solve_order(self.a, self.b)
        with vsc.implies(self.a != 0):
            self.b == 0


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveSolveOrder(VscTestCase):

    def setUp(self):
        super().setUp()
        random.seed(1)
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _count_s(self, ordered, n=2000):
        o = SImpliesD(ordered)
        n1 = 0
        for _ in range(n):
            o.randomize()
            if int(o.s) == 1:
                self.assertEqual(int(o.d), 0)
                n1 += 1
        return n1

    def test_unordered_s_is_rare(self):
        # One solution has s == 1, 2^32 have s == 0.
        self.assertLess(self._count_s(False), 10)

    def test_solve_s_before_d(self):
        n1 = self._count_s(True)
        self.assertTrue(850 < n1 < 1150, "s==1 in %d of 2000" % n1)

    def test_order_beats_smallest_domain_first(self):
        n = 4000
        o = WideBeforeNarrow()
        zeros = 0
        seen = set()
        for _ in range(n):
            o.randomize()
            a = int(o.a)
            if a != 0:
                self.assertEqual(int(o.b), 0)
            zeros += a == 0
            seen.add(a)
        self.assertLess(zeros, 0.02 * n)
        self.assertGreater(len(seen), 240)
