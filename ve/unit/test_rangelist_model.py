from unittest import TestCase

from vsc.model.rangelist_model import RangelistModel


class TestRangelistModel(TestCase):

    def test_intersect_exclusions(self):
        cases = [
            # Removing a range must not leave an invalid index for the
            # next exclusion, including when no ranges remain.
            ([0], [0, 1], []),
            ([0, 1], [0, 1], []),
            ([0, 2, 4], [2, 4], [[0, 0]]),
            ([0, 1, 2], [0, 1], [[2, 2]]),
            # Splits and trims must still apply every exclusion to all
            # surviving ranges, regardless of exclusion order.
            ([[0, 10]], [5, [0, 4], [6, 8]], [[9, 10]]),
            ([[0, 10]], [[6, 8], [0, 4], 5], [[9, 10]]),
            ([[0, 10]], [[2, 4], [6, 8]], [[0, 1], [5, 5], [9, 10]]),
            ([[0, 2], [4, 6]], [[1, 5]], [[0, 0], [6, 6]]),
            ([], [0, 1], []),
            ([[0, 2]], [], [[0, 2]]),
        ]

        for ranges, exclusions, expected in cases:
            with self.subTest(ranges=ranges, exclusions=exclusions):
                model = RangelistModel(ranges)
                other = RangelistModel(exclusions)
                original_exclusions = other.clone()

                model.intersect(other)

                self.assertEqual(model.range_l, expected)
                self.assertTrue(other.equals(original_exclusions))
