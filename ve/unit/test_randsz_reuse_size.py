'''
A random-size array's size is solved before the constraints that read its
elements, and the dv-solve translator builds ``x in arr`` and ``arr.sum`` over
the solved prefix. The compiled problem is cached and reused while the RandSet
looks the same, so it must be rebuilt once the size is solved differently.
It was not: ``a in arr`` kept matching elements past the new size, and failed
on about a third of the solves.
'''
import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class InArr(object):

    def __init__(self):
        self.a = vsc.rand_uint8_t()
        self.arr = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.arr.size > 0
        self.arr.size <= 4
        self.a in self.arr


@vsc.randobj
class SumArr(object):

    def __init__(self):
        self.arr = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.arr.size > 0
        self.arr.size <= 4
        self.arr.sum == 20


class TestRandszReuseSize(VscTestCase):

    def test_in_follows_the_solved_size(self):
        o = InArr()
        sizes = set()
        for _ in range(60):
            o.randomize()
            self.assertIn(o.a, list(o.arr), "a=%d arr=%r" % (o.a, list(o.arr)))
            sizes.add(len(o.arr))
        self.assertGreater(len(sizes), 1)

    def test_sum_follows_the_solved_size(self):
        o = SumArr()
        sizes = set()
        for _ in range(60):
            o.randomize()
            self.assertEqual(sum(o.arr), 20, "arr=%r" % list(o.arr))
            sizes.add(len(o.arr))
        self.assertGreater(len(sizes), 1)
