'''
RandState.draw -- the uniform inclusive draw used by the direct-draw
(unconstrained + T0) path in place of Random.randint.

It is a hand-written rejection sampler, so it gets its own tests: an off-by-one
in the bit width or the rejection bound is a distribution bug that no
constraint check would catch (every value it returns is still in range).
'''
import unittest

from vsc.model.rand_state import RandState


class TestRandStateDraw(unittest.TestCase):

    def setUp(self):
        self.rs = RandState("t")

    def test_support_is_exactly_the_range(self):
        for lo, hi in ((0, 1), (0, 2), (3, 9), (-4, 4), (7, 7)):
            with self.subTest(lo=lo, hi=hi):
                seen = set(self.rs.draw(lo, hi) for _ in range(4000))
                self.assertEqual(seen, set(range(lo, hi + 1)))

    def test_uniform(self):
        lo, hi, n = 0, 6, 70000
        counts = [0] * (hi - lo + 1)
        for _ in range(n):
            counts[self.rs.draw(lo, hi) - lo] += 1
        exp = n / len(counts)
        chi2 = sum((c - exp) ** 2 / exp for c in counts)
        # 6 dof: the 0.001 critical value is 22.5.
        self.assertLess(chi2, 22.5, counts)

    def test_power_of_two_range(self):
        # n == 2^k exercises the branch where the rejection loop never rejects.
        counts = {}
        for _ in range(32000):
            v = self.rs.draw(0, 255)
            counts[v] = counts.get(v, 0) + 1
        self.assertEqual(len(counts), 256)

    def test_wide_range(self):
        lo, hi = 0, (1 << 64) - 1
        vals = [self.rs.draw(lo, hi) for _ in range(2000)]
        self.assertTrue(all(lo <= v <= hi for v in vals))
        self.assertGreater(max(vals), 1 << 62)
        self.assertLess(min(vals), 1 << 62)

    def test_single_value(self):
        self.assertEqual(self.rs.draw(5, 5), 5)

    def test_reversed_range_does_not_hang(self):
        self.assertEqual(self.rs.draw(9, 3), 9)

    def test_deterministic_for_a_seed(self):
        a = [RandState("s").draw(0, 1000) for _ in range(1)]
        b = [RandState("s").draw(0, 1000) for _ in range(1)]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
