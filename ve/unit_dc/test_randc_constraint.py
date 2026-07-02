'''
Dataclass-front-end adaptation of t_randc_constraint.v.

randc combined with ordinary constraints: the cyclic domain is the *constraint-
satisfying* subset, and over N full cycles each satisfying value appears exactly N
times while excluded values never appear. Covers a range constraint, an exclude
constraint, and constraint inheritance (a derived class further narrows an
inherited randc's domain).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandcConstraint(DcTestCase):

    def _assert_uniform_cycles(self, c, valid, cycles, read=lambda c: int(c.x)):
        count = {v: 0 for v in valid}
        for _ in range(cycles):
            window = []
            for _ in range(len(valid)):
                c.randomize()
                v = read(c)
                self.assertIn(v, valid, "produced out-of-domain value")
                window.append(v)
                count[v] += 1
            self.assertEqual(sorted(window), sorted(valid))
        for v in valid:
            self.assertEqual(count[v], cycles)

    def test_range_constraint(self):
        # RandcRange: randc bit[3:0] with 3 <= value <= 10 cycles over {3..10}.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u4 = vdc.randc()

            @vdc.constraint
            def c_range(self):
                self.x >= 3
                self.x <= 10

        self._assert_uniform_cycles(my_c(), list(range(3, 11)), cycles=3)

    def test_exclude_constraint(self):
        # RandcSmall: randc bit[1:0] with val != 0 cycles over {1,2,3}.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u2 = vdc.randc()

            @vdc.constraint
            def c_exclude(self):
                self.x != 0

        self._assert_uniform_cycles(my_c(), [1, 2, 3], cycles=4)

    def test_inheritance_further_restrict(self):
        # RandcParent (code > 0) extended by RandcChild (code <= 5): the child
        # cycles over the intersection {1..5} of inherited + added constraints.
        @vdc.dataclass
        class Parent(vdc.RandClass):
            x: vdc.u3 = vdc.randc()   # 3-bit: 0..7

            @vdc.constraint
            def c_positive(self):
                self.x > 0

        @vdc.dataclass
        class Child(Parent):
            @vdc.constraint
            def c_upper(self):
                self.x <= 5

        # Parent alone cycles over {1..7}.
        self._assert_uniform_cycles(Parent(), list(range(1, 8)), cycles=3)
        # Child cycles over the inherited+added intersection {1..5}.
        self._assert_uniform_cycles(Child(), list(range(1, 6)), cycles=4)
