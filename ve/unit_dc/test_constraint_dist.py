'''
Dataclass-front-end parallel of ve/unit/test_constraint_dist.py.

P2 static-weight subset: in_range, static_zero_weight, static_weights,
static_weight_ranges. Dynamic-weight dist (weight value is a field, e.g.
vsc.weight(1, self.en_one)) is a follow-on (the dc parser currently takes constant
weights), as are the conditional-weight cases.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintDist(DcTestCase):

    def test_dist_in_range(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_a(self):
                vdc.dist(self.a, [
                    vdc.weight(1, 10),
                    vdc.weight(2, 20),
                    vdc.weight(4, 40),
                    vdc.weight(8, 80)])

        c = my_c()
        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1, 2, 4, 8])

    def test_dist_static_zero_weight(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_a(self):
                vdc.dist(self.a, [
                    vdc.weight(1, 10),
                    vdc.weight(2, 0),
                    vdc.weight(4, 40),
                    vdc.weight(8, 80)])

        c = my_c()
        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1, 4, 8])

    def test_dist_static_weights(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_a(self):
                vdc.dist(self.a, [
                    vdc.weight(1, 80),
                    vdc.weight(2, 40),
                    vdc.weight(3, 20),
                    vdc.weight(4, 10)])

        c = my_c()
        hist = 4 * [0]
        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1, 2, 3, 4])
            hist[c.a - 1] += 1

    def test_dist_static_weight_ranges(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_a(self):
                vdc.dist(self.a, [
                    vdc.weight((10, 15),  80),
                    vdc.weight((20, 30),  40),
                    vdc.weight((40, 70),  20),
                    vdc.weight((80, 100), 10)])

        c = my_c()
        hist = 4 * [0]
        for i in range(100):
            c.randomize()
            if 10 <= c.a <= 15:
                hist[0] += 1
            elif 20 <= c.a <= 30:
                hist[1] += 1
            elif 40 <= c.a <= 70:
                hist[2] += 1
            elif 80 <= c.a <= 100:
                hist[3] += 1
            else:
                self.fail("Value " + str(c.a) + " illegal")
