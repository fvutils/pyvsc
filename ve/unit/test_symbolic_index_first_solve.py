'''
A random index is chosen by the solve, so its value from before the solve must
not pick an element or a bit.

``arr[i] == 9`` with a random ``i`` used to be resolved, before solving, as
``arr[<i's current value>] == 9``. Boolector built it that way, so a fresh
object (i == 0) put the 9 in arr[0] while the solve chose another i. The bounds
pass did the same on both back-ends, pinning arr[0] to 9: dv-solve then wrote 9
into arr[0] on every solve as well as into arr[i]. A bit-select ``a[i]`` with a
random ``i`` read bit 0 the same way on both back-ends.
'''
from collections import Counter

import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class ArrIdx(object):

    def __init__(self):
        self.i = vsc.rand_uint8_t()
        self.arr = vsc.rand_list_t(vsc.uint8_t(), 4)

    @vsc.constraint
    def c(self):
        self.arr[self.i] == 9
        self.i == 2


@vsc.randobj
class ArrIdxFree(object):

    def __init__(self):
        self.i = vsc.rand_uint8_t()
        self.arr = vsc.rand_list_t(vsc.uint8_t(), 4)

    @vsc.constraint
    def c(self):
        self.i < 4
        self.arr[self.i] == 9


@vsc.randobj
class BitIdx(object):

    def __init__(self):
        self.i = vsc.rand_uint8_t()
        self.a = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        self.i < 8
        self.a[self.i] == 1


class TestSymbolicIndexFirstSolve(VscTestCase):

    def test_fresh_object_uses_solved_index(self):
        for _ in range(20):
            o = ArrIdx()
            o.randomize()
            self.assertEqual(o.i, 2)
            self.assertEqual(o.arr[2], 9)

    def test_other_elements_are_not_pinned(self):
        # Before the fix, arr[0] (the pre-solve i) was pinned to 9 as well.
        o = ArrIdx()
        arr0 = set()
        for _ in range(20):
            o.randomize()
            self.assertEqual(o.arr[2], 9)
            arr0.add(o.arr[0])
        self.assertGreater(len(arr0), 1)

    def test_index_and_element_move_together(self):
        seen = Counter()
        for _ in range(40):
            o = ArrIdxFree()
            o.randomize()
            self.assertEqual(o.arr[o.i], 9)
            seen[o.i] += 1
        self.assertGreater(len(seen), 1)

    def test_bit_select(self):
        seen = Counter()
        for _ in range(40):
            o = BitIdx()
            o.randomize()
            self.assertEqual((o.a >> o.i) & 1, 1, "a=%#x i=%d" % (o.a, o.i))
            seen[o.i] += 1
        self.assertGreater(len(seen), 1)

    def test_bit_select_reused_object(self):
        o = BitIdx()
        for _ in range(40):
            o.randomize()
            self.assertEqual((o.a >> o.i) & 1, 1, "a=%#x i=%d" % (o.a, o.i))


class TestSymbolicIndexOutOfRange(VscTestCase):
    """A random index whose current value is out of range must not be read
    as an element (B16): the array expansion and the randset builder did,
    and raised IndexError before solving."""

    def test_out_of_range_current_value(self):
        for _ in range(10):
            o = ArrIdxFree()
            o.i = 200
            o.randomize()
            self.assertLess(o.i, 4)
            self.assertEqual(o.arr[o.i], 9)

    def test_out_of_range_inline(self):
        o = ArrIdxFree()
        for _ in range(10):
            o.i = 200
            with o.randomize_with() as it:
                it.i < 2
            self.assertLess(o.i, 2)
            self.assertEqual(o.arr[o.i], 9)
