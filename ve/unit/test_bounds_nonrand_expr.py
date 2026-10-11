'''
The bounds pass pins a field's domain when it is equal to an expression that
reads no random field (``x == k + 1``, with ``k`` non-rand). Whether an
expression is non-rand was decided by the *last* field it read, so
``x == r + k`` (random ``r``, non-rand ``k``) counted as non-rand: ``x`` was
pinned to ``r + k`` evaluated before the solve, and dv-solve then always gave
``r == 0`` (B17). A sum over a random-size array, which has no elements before
the solve, counted as non-rand too, and the pass crashed calling ``val()`` on
it (B12).
'''
import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class RPlusK(object):

    def __init__(self):
        self.x = vsc.rand_uint8_t()
        self.r = vsc.rand_uint8_t()
        self.k = vsc.uint8_t(5)

    @vsc.constraint
    def c(self):
        self.r < 10
        self.x == self.r + self.k


@vsc.randobj
class KPlusR(RPlusK):

    @vsc.constraint
    def c(self):
        self.r < 10
        self.x == self.k + self.r


@vsc.randobj
class SumEqField(object):

    def __init__(self):
        self.t = vsc.rand_uint8_t()
        self.arr = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.arr.size > 0
        self.arr.size < 5
        self.arr.sum == self.t


class TestBoundsNonrandExpr(VscTestCase):

    def test_rand_plus_nonrand_not_pinned(self):
        for cls in (RPlusK, KPlusR):
            with self.subTest(cls=cls.__name__):
                o = cls()
                seen = set()
                for _ in range(40):
                    o.randomize()
                    self.assertEqual(o.x, o.r + o.k)
                    seen.add(o.r)
                self.assertGreater(len(seen), 3, seen)

    def test_randsz_sum_eq_field(self):
        o = SumEqField()
        for _ in range(20):
            o.randomize()
            self.assertTrue(1 <= len(o.arr) <= 4)
            self.assertEqual(sum(o.arr) & 0xFF, o.t)
