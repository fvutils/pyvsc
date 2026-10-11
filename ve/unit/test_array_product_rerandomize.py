'''
Boolector builds ``arr.product`` once and caches the node on the array model.
The cache was cleared after each randomize for ``arr.sum`` but not for
``arr.product``, so the next randomize used a node of a Boolector instance that
no longer existed: a crash, or a constraint that silently did nothing.
'''
import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class Prod(object):

    def __init__(self):
        self.arr = vsc.rand_list_t(vsc.uint8_t(), 3)

    @vsc.constraint
    def c(self):
        self.arr.product == 30


class TestArrayProductRerandomize(VscTestCase):

    def test_product_holds_on_every_randomize(self):
        o = Prod()
        for _ in range(20):
            o.randomize()
            self.assertEqual(o.arr[0] * o.arr[1] * o.arr[2], 30, list(o.arr))
