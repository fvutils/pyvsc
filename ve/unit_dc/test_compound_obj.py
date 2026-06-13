'''
Dataclass-front-end parallel of ve/unit/test_compound_obj.py.

Covers nested (composite) RandClass fields: a field typed as another
@vdc.dataclass RandClass becomes a nested FieldCompositeModel stitched into the
parent's solve tree. The classic front-end expresses these with
``vsc.rand_attr(C1())`` / ``vsc.attr(C1())``; in dc the nested instance is a plain
field whose annotation is the nested class, declared rand with ``vdc.rand()`` or
non-rand with ``vdc.field()``.

(List-of-object / array-of-composite cases land with the random-array composite
follow-on; this file pins the scalar-nested behavior.)
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class C1(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()


class TestCompoundObj(DcTestCase):

    def test_rand_compound(self):

        @vdc.dataclass
        class C2(vdc.RandClass):
            c1: C1 = vdc.rand()
            c2: C1 = vdc.rand()

        c2 = C2()
        seen = set()
        for _ in range(10):
            c2.randomize()
            # Each nested object is independently randomized.
            seen.add((c2.c1.a, c2.c1.b, c2.c2.a, c2.c2.b))
        # 10 draws over 16-bit subfields: overwhelmingly distinct.
        self.assertGreater(len(seen), 1)

    def test_cross_object_constraint(self):
        # Parent constraint relating two nested objects' fields (the enabled
        # analogue of the classic disabled_test_rand_compound_nonrand).

        @vdc.dataclass
        class C2(vdc.RandClass):
            c1: C1 = vdc.rand()
            c2: C1 = vdc.field()   # non-rand: solver holds its current value

            @vdc.constraint
            def c1_c2_c(self):
                self.c1.a == self.c2.a

        c2 = C2()
        for i in range(10):
            c2.c2.a = i
            c2.randomize()
            self.assertEqual(c2.c1.a, i)

    def test_nested_constraint_in_child(self):
        # A constraint declared on the *child* type must apply to nested instances.

        @vdc.dataclass
        class Child(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def lt_c(self):
                self.a < 3

        @vdc.dataclass
        class Parent(vdc.RandClass):
            x: Child = vdc.rand()
            y: Child = vdc.rand()

            @vdc.constraint
            def eq_c(self):
                self.x.a == self.y.a

        p = Parent()
        for _ in range(10):
            p.randomize()
            self.assertLess(p.x.a, 3)
            self.assertLess(p.y.a, 3)
            self.assertEqual(p.x.a, p.y.a)

    def test_two_layer(self):
        # Three-deep nesting with a constraint crossing two levels.

        @vdc.dataclass
        class Leaf(vdc.RandClass):
            v: vdc.u8 = vdc.rand()

            @vdc.constraint
            def rng_c(self):
                self.v < 20

        @vdc.dataclass
        class Mid(vdc.RandClass):
            leaf: Leaf = vdc.rand()

        @vdc.dataclass
        class Top(vdc.RandClass):
            m1: Mid = vdc.rand()
            m2: Mid = vdc.rand()

            @vdc.constraint
            def eq_c(self):
                self.m1.leaf.v == self.m2.leaf.v

        t = Top()
        for _ in range(10):
            t.randomize()
            self.assertLess(t.m1.leaf.v, 20)
            self.assertEqual(t.m1.leaf.v, t.m2.leaf.v)
