"""Uniform drawing over a multi-range (gapped) domain -- regression lock for D-1.

``Randomizer.randomize()`` assigns every *unconstrained* field directly from its
propagated bounds, with no solver involved. For a domain made of several disjoint
ranges that draw used to pick a **range index** uniformly and then return that
range's **lower endpoint**:

    idx = self.randstate.randint(0, len(range_l)-1)
    uf.set_val(range_l[idx][0])

which is wrong twice: ranges are weighted 1:1 regardless of how many values they
hold, and no interior value of any range is reachable at all. It was harmless only
for the enumerated case the code was written for, where every range is a single
value.

This matters beyond enums because the T0 tier promotes bound-only RandSets into
exactly this path, so genuine multi-range domains start flowing through it.

``test_enum_shape_is_bit_identical`` pins the compatibility requirement: when every
range is a point the new draw must consume the same single ``randstate`` call over
the same span and return the same value as the old code, so seeded enum results do
not move.
"""
from unittest import TestCase

from vsc.model.randomizer import Randomizer
from vsc.model.rand_state import RandState


def _mk(seed=0):
    return Randomizer(RandState(seed))


class TestMultiRangeDraw(TestCase):

    def test_all_values_reachable(self):
        """Every value of every range must be produced, not just the minima."""
        r = _mk()
        ranges = [[0, 3], [100, 104], [200, 200]]
        expect = set(range(0, 4)) | set(range(100, 105)) | {200}
        got = {r._draw_multi_range(ranges) for _ in range(4000)}
        self.assertEqual(got, expect)

    def test_uniform_over_the_union(self):
        """A big range must be favoured over a small one in proportion to size.

        Old behaviour: P(value == 0) == 1/2 (one of two ranges, lower endpoint).
        Correct behaviour: P(value == 0) == 1/1001.
        """
        r = _mk()
        ranges = [[0, 0], [1000, 1999]]
        n = 20000
        hits_small = sum(1 for _ in range(n)
                         if r._draw_multi_range(ranges) == 0)
        # Expected 20000/1001 ~= 20; the old code produced ~10000.
        self.assertLess(hits_small, 100)
        self.assertGreater(hits_small, 0)

    def test_no_value_dominates(self):
        """No single value should take an outsized share of a wide gapped domain."""
        r = _mk()
        ranges = [[0, 63], [1000, 1063]]
        n = 12800
        counts = {}
        for _ in range(n):
            v = r._draw_multi_range(ranges)
            counts[v] = counts.get(v, 0) + 1
        self.assertEqual(len(counts), 128)
        # Uniform share is 1/128 = 0.78%; allow generous slack, but the old
        # behaviour put 50% on each of two values.
        self.assertLess(max(counts.values()) / n, 0.05)

    def test_enum_shape_is_bit_identical(self):
        """Point-only ranges (the enum case) must not move a single seeded value.

        The old code drew ``randint(0, len(range_l)-1)`` and returned
        ``range_l[idx][0]``. When every range is a point, ``total == len(range_l)``,
        so the new code draws from an identical span and maps index -> that range's
        only value. Same call count, same span, same result.
        """
        ranges = [[1, 1], [3, 3], [7, 7], [9, 9]]

        new = _mk(12)
        got = [new._draw_multi_range(ranges) for _ in range(500)]

        old_state = _mk(12)
        expect = []
        for _ in range(500):
            idx = old_state.randstate.randint(0, len(ranges) - 1)
            expect.append(ranges[idx][0])

        self.assertEqual(got, expect)

    def test_single_range_endpoints_included(self):
        r = _mk()
        got = {r._draw_multi_range([[5, 7]]) for _ in range(200)}
        self.assertEqual(got, {5, 6, 7})

    def test_degenerate_empty_domain_does_not_raise(self):
        """An empty/reversed domain must not raise here; the solve path reports it."""
        r = _mk()
        self.assertEqual(r._draw_multi_range([[5, 4]]), 5)
