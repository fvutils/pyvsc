'''
Dataclass-front-end parallel of ve/unit/test_list_scalar.py.

Random-size scalar lists with element-ordering constraints. The fixedsz/temp,
enum-list, and queue cases land with their respective follow-ons.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestListScalar(DcTestCase):

    def test_randsz_smoke(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand()

            @vdc.constraint
            def l_c(self):
                self.l.size in vdc.rangelist(vdc.rng(2, 10))
                self.l[1] == (self.l[0] + 1)

        it = my_item_c()
        it.randomize()
        self.assertEqual(it.l[1], it.l[0] + 1)

    def test_randsz_len(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand()

            @vdc.constraint
            def l_c(self):
                self.l.size in vdc.rangelist(vdc.rng(2, 10))
                self.l[1] == (self.l[0] + 1)

        it = my_item_c()
        it.randomize()
        self.assertGreaterEqual(len(it.l), 2)
        self.assertLessEqual(len(it.l), 10)
        self.assertEqual(it.l[1], it.l[0] + 1)

    def test_randsz_foreach_idx(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand()
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def l_c(self):
                self.l.size in vdc.rangelist(vdc.rng(2, 10))

                with vdc.foreach(self.l, it=False, idx=True) as idx:
                    with vdc.if_then(idx > 0):
                        self.l[idx] == self.l[idx - 1] + 1

        it = my_item_c()
        it.randomize()
        for i in range(len(it.l)):
            if i > 0:
                self.assertEqual(it.l[i], it.l[i - 1] + 1)

    def test_randsz_max_size_bounds(self):
        # B15: max_size= on a scalar array was ignored. Without a size
        # constraint randomize() failed ("exceeds 100000"); with a looser one
        # the size went past max_size.

        @vdc.dataclass
        class unbounded(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand(max_size=6)

        @vdc.dataclass
        class loose(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand(max_size=6)

            @vdc.constraint
            def c(self):
                self.l.size >= 3
                self.l.size < 20

        @vdc.dataclass
        class over(vdc.RandClass):
            l: list[vdc.u8] = vdc.rand(max_size=6)

            @vdc.constraint
            def c(self):
                self.l.size == 7

        u, lo = unbounded(), loose()
        sizes = set()
        for _ in range(40):
            u.randomize()
            self.assertLessEqual(len(u.l), 6)
            lo.randomize()
            self.assertTrue(3 <= len(lo.l) <= 6, len(lo.l))
            sizes.add(len(lo.l))
        self.assertEqual(sizes, {3, 4, 5, 6})
        with self.assertRaises(vdc.SolveFailure):
            over().randomize()
