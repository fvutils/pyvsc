'''
Dataclass-front-end parallel of ve/unit/test_list_object.py (object/composite
arrays).

A ``list[Sub]`` field where ``Sub`` is a @vdc.dataclass RandClass is a composite
array: each element's FieldCompositeModel is stitched into a non-scalar
FieldArrayModel (the same shape classic ``rand_list_t(Sub())`` builds). This file
pins fixed-size composite arrays with constant-index element access; foreach over
composite arrays is exercised in test_constraint_foreach.py.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class Sub(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def lt_c(self):
        self.a < 5


class TestListObject(DcTestCase):

    def test_element_constraints_apply(self):
        # Each element's own constraint must hold across the whole array.

        @vdc.dataclass
        class Top(vdc.RandClass):
            arr: list[Sub] = vdc.rand(size=4)

        t = Top()
        for _ in range(10):
            t.randomize()
            self.assertEqual(len(t.arr), 4)
            self.assertTrue(all(e.a < 5 for e in t.arr))

    def test_const_index_cross_element(self):
        # Parent constraint relating two elements by constant index.

        @vdc.dataclass
        class Top(vdc.RandClass):
            arr: list[Sub] = vdc.rand(size=3)

            @vdc.constraint
            def eq_c(self):
                self.arr[0].a == self.arr[1].a
                self.arr[2].a == 1

        t = Top()
        for _ in range(10):
            t.randomize()
            self.assertEqual(t.arr[0].a, t.arr[1].a)
            self.assertLess(t.arr[0].a, 5)
            self.assertEqual(t.arr[2].a, 1)

    def test_array_of_nested_composite(self):
        # Array element is itself a composite holding a nested composite:
        # self.a[i].b.c — index, attr, attr.

        @vdc.dataclass
        class Leaf(vdc.RandClass):
            c: vdc.u8 = vdc.rand()

            @vdc.constraint
            def rng_c(self):
                self.c < 20

        @vdc.dataclass
        class Mid(vdc.RandClass):
            b: Leaf = vdc.rand()

        @vdc.dataclass
        class Parent(vdc.RandClass):
            a: list[Mid] = vdc.rand(size=2)

            @vdc.constraint
            def eq_c(self):
                self.a[0].b.c == self.a[1].b.c

        p = Parent()
        for _ in range(10):
            p.randomize()
            self.assertLess(p.a[0].b.c, 20)
            self.assertEqual(p.a[0].b.c, p.a[1].b.c)

    def test_foreach_element(self):
        # foreach over a composite array binds `it` to each element (unrolled).

        @vdc.dataclass
        class Top(vdc.RandClass):
            arr: list[Sub] = vdc.rand(size=4)

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.arr) as it:
                    it.a == 3

        t = Top()
        for _ in range(5):
            t.randomize()
            self.assertTrue(all(e.a == 3 for e in t.arr))

    def test_foreach_idx_cross(self):
        # foreach with idx relating element i to element i across two arrays.

        @vdc.dataclass
        class Top(vdc.RandClass):
            xs: list[Sub] = vdc.rand(size=3)
            ys: list[Sub] = vdc.rand(size=3)

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.xs, idx=True) as i:
                    self.xs[i].a == self.ys[i].a

        t = Top()
        for _ in range(5):
            t.randomize()
            for i in range(3):
                self.assertEqual(t.xs[i].a, t.ys[i].a)
                self.assertLess(t.xs[i].a, 5)

    def test_randsize_obj_array(self):
        # Random-size composite array: max_size pre-allocates the upper bound,
        # the solver picks size within the user's constraint, and len(arr) is the
        # solved size. Mirrors classic test_obj_array (randsz_list_t of objects).

        @vdc.dataclass
        class Top(vdc.RandClass):
            a: list[Sub] = vdc.rand(max_size=5)

            @vdc.constraint
            def a_c(self):
                self.a.size < 5
                self.a.size > 1

        t = Top()
        for _ in range(10):
            t.randomize()
            self.assertGreater(len(t.a), 1)
            self.assertLess(len(t.a), 5)
            # Each exposed element is a constrained Sub.
            self.assertTrue(all(e.a < 5 for e in t.a))

    def test_size_in_constraint(self):
        # arr.size is the (fixed) element count, usable in a constraint value.

        @vdc.dataclass
        class Top(vdc.RandClass):
            arr: list[Sub] = vdc.rand(size=3)
            n: vdc.u8 = vdc.rand()

            @vdc.constraint
            def n_c(self):
                self.n == self.arr.size

        t = Top()
        t.randomize()
        self.assertEqual(t.n, 3)

    # --- t_constraint_cls_arr_member: constraints on object-array members --- #
    def test_foreach_member_range(self):
        # Scenario A: foreach range on each element's member.

        @vdc.dataclass
        class Item(vdc.RandClass):
            value: vdc.u8 = vdc.rand()

        @vdc.dataclass
        class Container(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)

            @vdc.constraint
            def val_c(self):
                with vdc.foreach(self.items) as it:
                    it.value in vdc.rangelist((10, 200))

        c = Container()
        for _ in range(20):
            c.randomize()
            for e in c.items:
                self.assertTrue(10 <= int(e.value) <= 200)

    def test_foreach_member_relative_index_order(self):
        # Scenario B: foreach ordering via a relative index (items[i] > items[i-1]).
        # Exercises constant-folded composite-array subscripts (i-1) at lower time.

        @vdc.dataclass
        class Item(vdc.RandClass):
            value: vdc.u8 = vdc.rand()

        @vdc.dataclass
        class Container(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)

            @vdc.constraint
            def order_c(self):
                with vdc.foreach(self.items, idx=True) as i:
                    with vdc.if_then(i != 0):
                        self.items[i].value > self.items[i - 1].value

        c = Container()
        for _ in range(20):
            c.randomize()
            vals = [int(e.value) for e in c.items]
            self.assertTrue(all(vals[k] > vals[k - 1] for k in range(1, 4)),
                            "ordering violated: %s" % vals)

    def test_const_index_member_order_chain(self):
        # Scenario C: the same ordering written with explicit constant indices.

        @vdc.dataclass
        class Item(vdc.RandClass):
            value: vdc.u8 = vdc.rand()

        @vdc.dataclass
        class Container(vdc.RandClass):
            items: list[Item] = vdc.rand(size=4)

            @vdc.constraint
            def val_c(self):
                self.items[0].value < self.items[1].value
                self.items[1].value < self.items[2].value
                self.items[2].value < self.items[3].value

        c = Container()
        for _ in range(20):
            c.randomize()
            vals = [int(e.value) for e in c.items]
            self.assertTrue(all(vals[k] > vals[k - 1] for k in range(1, 4)),
                            "ordering violated: %s" % vals)
