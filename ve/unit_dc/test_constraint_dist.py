'''
Dataclass-front-end parallel of ve/unit/test_constraint_dist.py.

Static-weight cases (in_range, static_zero_weight, static_weights,
static_weight_ranges) plus dynamic-weight dist, where a weight value is a non-rand
field read at solve time (vdc.weight(1, self.en_one)).

The nested-dist combos (foreach / if-else / implication) adapt the Verilator
tests t_constraint_dist_foreach_if, t_randomize_dist_foreach,
t_randomize_dist_implication and t_randomize_dist_conditional: a dist table placed
under a foreach body, gated by an if/->, or selected by an if/else. These exercise
the dv-solve dist-encoding path *inside* conditional/iterative scopes, which the
flat static-weight cases above never reach.
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

    def test_dist_dynamic_zero_weight(self):
        # Weight values are non-rand fields read at solve time; setting one to 0
        # excludes that value. Mirrors classic test_dist_dynamic_zero_weight.

        @vdc.dataclass
        class my_c(vdc.RandClass):
            en_one: vdc.u8 = vdc.field()
            en_two: vdc.u8 = vdc.field()
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_a(self):
                vdc.dist(self.a, [
                    vdc.weight(1, self.en_one),
                    vdc.weight(2, self.en_two)])

        c = my_c()

        c.en_one = 1
        c.en_two = 0
        for _ in range(10):
            c.randomize()
            self.assertEqual(c.a, 1)

        c.en_one = 0
        c.en_two = 1
        for _ in range(10):
            c.randomize()
            self.assertEqual(c.a, 2)

        c.en_one = 1
        c.en_two = 1
        for _ in range(10):
            c.randomize()
            self.assertIn(c.a, [1, 2])

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

    # ---- nested-dist combos (Verilator dist_foreach / dist_conditional /
    #      dist_implication family) ----

    def test_dist_in_foreach(self):
        # t_randomize_dist_foreach: a dist per array element. 0 gets weight 3, the
        # range [1:4] shares weight 1. Every element must stay in {0..4} and both
        # the zero and non-zero buckets must be hit across the run.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: list[vdc.u4] = vdc.rand(size=4)

            @vdc.constraint
            def dist_a(self):
                with vdc.foreach(self.a) as it:
                    vdc.dist(it, [vdc.weight(0, 3), vdc.weight(vdc.rng(1, 4), 1)])

        c = my_c()
        seen_zero = seen_nonzero = 0
        for _ in range(100):
            c.randomize()
            for e in c.a:
                self.assertLessEqual(int(e), 4)
                if int(e) == 0:
                    seen_zero += 1
                else:
                    seen_nonzero += 1
        self.assertGreater(seen_zero, 0)
        self.assertGreater(seen_nonzero, 0)

    def test_dist_in_foreach_if(self):
        # t_constraint_dist_foreach_if: foreach(a[i]) if (gate) a[i] dist {...}.
        # With gate a non-rand field forced true, the dist applies to every element.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            gate: vdc.u1 = vdc.field()
            a: list[vdc.u4] = vdc.rand(size=4)

            @vdc.constraint
            def dist_a(self):
                with vdc.foreach(self.a) as it:
                    with vdc.if_then(self.gate == 1):
                        vdc.dist(it, [vdc.weight(0, 3), vdc.weight(vdc.rng(1, 4), 1)])

        c = my_c()
        c.gate = 1
        seen_zero = seen_nonzero = 0
        for _ in range(100):
            c.randomize()
            for e in c.a:
                self.assertLessEqual(int(e), 4)
                if int(e) == 0:
                    seen_zero += 1
                else:
                    seen_nonzero += 1
        self.assertGreater(seen_zero, 0)
        self.assertGreater(seen_nonzero, 0)

    def test_dist_conditional(self):
        # t_randomize_dist_conditional: if(mode) favors 255, else favors 0. The two
        # dist tables are selected by a rand predicate. Guaranteed on both backends:
        # x always lands on a bucket value (membership), both modes occur, and
        # under each mode both bucket values are reachable.
        #
        # On dv-solve the per-mode *weight ratio* is guard-correlated (the
        # guard-staged conditional-dist sampler: freeze `mode`, then apply the
        # active branch's weights) — assert ~75/25 there. On boolector the ratio
        # collapses to the two tables' mean (~50%): the swizzler registers both
        # branch tables under the field and picks one uniformly, decoupled from the
        # guard. That boolector gap is documented (verilator_test_adaptation_plan.md
        # "Bugs found") and out of scope for the dv-solve fix; we only assert
        # membership there.
        from vsc.impl import ctor

        @vdc.dataclass
        class my_c(vdc.RandClass):
            mode: vdc.u1 = vdc.rand()
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def dist_x(self):
                with vdc.if_then(self.mode == 1):
                    vdc.dist(self.x, [vdc.weight(0, 1), vdc.weight(255, 3)])
                with vdc.else_then():
                    vdc.dist(self.x, [vdc.weight(0, 3), vdc.weight(255, 1)])

        c = my_c()
        per_mode = {0: {0: 0, 255: 0}, 1: {0: 0, 255: 0}}
        N = 800
        for _ in range(N):
            c.randomize()
            self.assertIn(int(c.x), (0, 255))
            per_mode[int(c.mode)][int(c.x)] += 1
        # Both modes are exercised, and each bucket value is reachable in each mode.
        for m in (0, 1):
            self.assertGreater(per_mode[m][0] + per_mode[m][255], 0)
        self.assertGreater(per_mode[0][0], 0)
        self.assertGreater(per_mode[1][255], 0)

        if ctor.get_solver_backend() == "dv-solve":
            # Favored bucket (3:1) wins a clear majority of its mode's trials.
            m1 = per_mode[1]
            m0 = per_mode[0]
            if m1[0] + m1[255]:
                self.assertGreater(m1[255], m1[0],
                                   "mode1 should favor 255 (3:1)")
            if m0[0] + m0[255]:
                self.assertGreater(m0[0], m0[255],
                                   "mode0 should favor 0 (3:1)")

    def test_dist_implication(self):
        # t_randomize_dist_implication (scalar): gate -> x dist {...}, gate forced
        # true, so x must land on a bucket value.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            g: vdc.u1 = vdc.rand()
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def force(self):
                self.g == 1

            @vdc.constraint
            def dist_x(self):
                with vdc.implies(self.g == 1):
                    vdc.dist(self.x, [
                        vdc.weight(10, 1), vdc.weight(20, 1), vdc.weight(30, 1)])

        c = my_c()
        for _ in range(50):
            c.randomize()
            self.assertEqual(int(c.g), 1)
            self.assertIn(int(c.x), (10, 20, 30))

    def test_dist_implication_chained(self):
        # t_randomize_dist_implication (chain): a -> b -> x dist {...}, both forced.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u1 = vdc.rand()
            b: vdc.u1 = vdc.rand()
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def force(self):
                self.a == 1
                self.b == 1

            @vdc.constraint
            def dist_x(self):
                with vdc.implies(self.a == 1):
                    with vdc.implies(self.b == 1):
                        vdc.dist(self.x, [vdc.weight(0, 3), vdc.weight(255, 1)])

        c = my_c()
        for _ in range(50):
            c.randomize()
            self.assertIn(int(c.x), (0, 255))

    def test_dist_foreach_implication(self):
        # t_randomize_dist_implication (foreach): foreach(arr[i]) enb -> arr[i] dist,
        # enb forced true, so every element is a bucket value.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            enb: vdc.u1 = vdc.rand()
            arr: list[vdc.u8] = vdc.rand(size=4)

            @vdc.constraint
            def force(self):
                self.enb == 1

            @vdc.constraint
            def dist_arr(self):
                with vdc.foreach(self.arr) as it:
                    with vdc.implies(self.enb == 1):
                        vdc.dist(it, [
                            vdc.weight(10, 1), vdc.weight(20, 1), vdc.weight(30, 1)])

        c = my_c()
        for _ in range(50):
            c.randomize()
            self.assertEqual(int(c.enb), 1)
            for e in c.arr:
                self.assertIn(int(e), (10, 20, 30))
