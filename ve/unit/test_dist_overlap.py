"""`dist` entries that overlap: a value or range listed inside another
entry's range. Runs on whichever solver the suite selects.
"""
import vsc
from vsc_test_case import VscTestCase


class TestDistOverlap(VscTestCase):

    def _values(self, obj, n=400):
        seen = set()
        for _ in range(n):
            obj.randomize()
            seen.add(int(obj.a))
        return seen

    def test_value_inside_a_range_keeps_the_range_end(self):
        """`[10:13] :/ 1, 12 := 1`: the field's bound was cut to [10..12]
        when the merge of the dist's ranges took the inner range's end, so
        13 could never be drawn on a solver that declares that bound."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                vsc.dist(s.a, [vsc.weight((10, 13), 1), vsc.weight(12, 1)])

        self.assertEqual(self._values(C()), {10, 11, 12, 13})
