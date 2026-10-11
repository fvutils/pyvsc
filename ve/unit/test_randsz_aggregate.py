'''
A sum or product over a random-size array, and its size (B18).

The aggregate was built from the size's value before the solve. Solved on its
own first, the size could make the aggregate unsatisfiable (size 0 for
``sum == 30``: ~20% of solves failed). Solved together with the elements (a
random index, or ``arr[-1]``), the aggregate was taken over the stale size and
the result was silently wrong. The size is now solved with the aggregate, and
both back-ends count element ``i`` only when ``i < size``.
'''
import math

import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class SumOnly(object):

    def __init__(self):
        self.arr = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.arr.size < 5
        self.arr.sum == 30


@vsc.randobj
class SumAndIndex(object):

    def __init__(self):
        self.arr = vsc.randsz_list_t(vsc.uint8_t())
        self.i = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        self.arr.size >= 2
        self.arr.size <= 8
        self.arr.sum == 100
        self.i < self.arr.size
        self.arr[self.i] == 7


@vsc.randobj
class ProductOnly(object):

    def __init__(self):
        self.arr = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.arr.size < 5
        self.arr.product == 30


class TestRandszAggregate(VscTestCase):

    def test_sum_never_fails(self):
        for seed in range(40):
            o = SumOnly()
            o.set_randstate(vsc.RandState.mkFromSeed(seed))
            o.randomize()
            self.assertEqual(sum(o.arr), 30)
            self.assertTrue(1 <= len(o.arr) <= 4)

    def test_sum_with_a_random_index(self):
        o = SumAndIndex()
        sizes = set()
        for _ in range(30):
            o.randomize()
            self.assertEqual(sum(o.arr), 100, list(o.arr))
            self.assertEqual(o.arr[o.i], 7)
            sizes.add(len(o.arr))
        self.assertGreater(len(sizes), 2)

    def test_product_never_fails(self):
        for seed in range(40):
            o = ProductOnly()
            o.set_randstate(vsc.RandState.mkFromSeed(seed))
            o.randomize()
            self.assertEqual(math.prod(o.arr), 30)
