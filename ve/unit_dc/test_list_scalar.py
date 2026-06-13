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
