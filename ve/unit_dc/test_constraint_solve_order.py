'''
Dataclass-front-end parallel of ve/unit/test_constraint_solve_order.py.

The classic file's active tests check runtime misuse-detection (solve_order outside
a constraint scope, buried in if_then, non-field args) — artifacts of the
operator-overloading runtime that have no dc analogue (the dc parser validates
solve_order structurally at decoration time; per plan §6 those stay classic-only).
Its model-introspection tests are `disabled_`. Here we assert the *functional*
guarantee: solve_order yields valid solutions under an ordered dependency.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintSolveOrder(DcTestCase):

    def test_order_solves(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                vdc.solve_order(self.a, self.b)
                self.a < self.b
                with vdc.if_then(self.a == 0):
                    self.b < 10

        i = my_c()
        for _ in range(50):
            i.randomize()
            self.assertLess(i.a, i.b)
            if i.a == 0:
                self.assertLess(i.b, 10)

    # ---- solve...before combos (Verilator t_constraint_solve_before /
    #      t_randomize_solve_before_foreach) ----

    def test_conditional_dependency(self):
        # t_constraint_solve_before Packet: solve mode before data, then the data
        # constraint branches on mode. Phased solving must pick mode first, then a
        # data value legal for that mode. Also assert mode spans its whole range
        # (the 'before' var isn't skewed away from mode==0 by the data branch).
        @vdc.dataclass
        class Packet(vdc.RandClass):
            mode: vdc.u3 = vdc.rand()
            data: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c_order(self):
                vdc.solve_order(self.mode, self.data)
                self.mode <= 3
                with vdc.if_then(self.mode == 0):
                    self.data == 0
                with vdc.else_if(self.mode == 1):
                    self.data.inside(vdc.rangelist(vdc.rng(1, 15)))
                with vdc.else_then():
                    self.data < 0x80

        p = Packet()
        modes_seen = set()
        for _ in range(60):
            p.randomize()
            self.assertLessEqual(int(p.mode), 3)
            modes_seen.add(int(p.mode))
            if int(p.mode) == 0:
                self.assertEqual(int(p.data), 0)
            elif int(p.mode) == 1:
                self.assertTrue(1 <= int(p.data) <= 15)
            else:
                self.assertLess(int(p.data), 0x80)
        # solve...before should not starve any mode value.
        self.assertEqual(modes_seen, {0, 1, 2, 3})

    def test_range_dependency(self):
        # t_constraint_solve_before Simple: solve x before y; x in [1:5]; y > x;
        # y < 0xf. y depends on the already-chosen x.
        @vdc.dataclass
        class Simple(vdc.RandClass):
            x: vdc.u4 = vdc.rand()
            y: vdc.u4 = vdc.rand()

            @vdc.constraint
            def c(self):
                vdc.solve_order(self.x, self.y)
                self.x.inside(vdc.rangelist(vdc.rng(1, 5)))
                self.y > self.x
                self.y < 0xf

        s = Simple()
        for _ in range(50):
            s.randomize()
            self.assertTrue(1 <= int(s.x) <= 5)
            self.assertTrue(int(s.x) < int(s.y) < 0xf)

    def test_multilevel_chain(self):
        # t_constraint_solve_before MultiLevel: a->b->c chained solve order with a
        # strictly increasing dependency chain.
        @vdc.dataclass
        class MultiLevel(vdc.RandClass):
            a: vdc.u4 = vdc.rand()
            b: vdc.u4 = vdc.rand()
            c: vdc.u4 = vdc.rand()

            @vdc.constraint
            def c_order(self):
                vdc.solve_order(self.a, self.b)
                vdc.solve_order(self.b, self.c)
                self.a.inside(vdc.rangelist(vdc.rng(1, 3)))
                self.b > self.a
                self.b < 8
                self.c > self.b
                self.c < 0xf

        m = MultiLevel()
        for _ in range(50):
            m.randomize()
            self.assertTrue(1 <= int(m.a) <= 3)
            self.assertTrue(int(m.a) < int(m.b) < 8)
            self.assertTrue(int(m.b) < int(m.c) < 0xf)

    def test_solve_before_in_foreach(self):
        # t_randomize_solve_before_foreach: solve mode before each element inside a
        # foreach; every element branches on the already-solved mode.
        @vdc.dataclass
        class Item(vdc.RandClass):
            mode: vdc.u4 = vdc.rand()
            data: list[vdc.u8] = vdc.rand(size=4)

            @vdc.constraint
            def mode_c(self):
                self.mode <= 3

            @vdc.constraint
            def data_c(self):
                with vdc.foreach(self.data) as it:
                    vdc.solve_order(self.mode, it)
                    with vdc.if_then(self.mode == 0):
                        it == 0
                    with vdc.else_then():
                        it.inside(vdc.rangelist(vdc.rng(1, 255)))

        it = Item()
        for _ in range(50):
            it.randomize()
            self.assertLessEqual(int(it.mode), 3)
            for e in it.data:
                if int(it.mode) == 0:
                    self.assertEqual(int(e), 0)
                else:
                    self.assertTrue(1 <= int(e) <= 255)
