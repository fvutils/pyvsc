'''
Dataclass-front-end adaptation of t_constraint_state.v.

Constraints that read *non-rand* state: a plain (``vdc.field()``) scalar set
between solves, and non-rand sub-object fields. The solver treats them as fixed
inputs -- ``rf == state`` pins a rand field to the current state value, and
``a > foo.x; a < bar.y`` bounds a rand field by two non-rand sub-object fields.
Changing the state between randomize() calls changes the solution.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class Foo(vdc.RandClass):
    x: vdc.u8 = vdc.field()    # non-rand sub-object field


@vdc.dataclass
class Bar(vdc.RandClass):
    y: vdc.u8 = vdc.field()


@vdc.dataclass
class Packet(vdc.RandClass):
    rf: vdc.u8 = vdc.rand()
    state: vdc.u8 = vdc.field()         # non-rand scalar state
    a: vdc.u8 = vdc.rand()
    foo: Foo = vdc.field()
    bar: Bar = vdc.field()

    @vdc.constraint
    def c1(self):
        self.rf == self.state

    @vdc.constraint
    def c2(self):
        self.a > self.foo.x
        self.a < self.bar.y


class TestConstraintState(DcTestCase):

    def test_state_and_subobj_bounds(self):
        p = Packet()
        p.foo.x = 10
        p.bar.y = 20

        # rf tracks the non-rand state; a stays within the sub-object bounds.
        for s in (3, 234, 99):
            p.state = s
            for _ in range(10):
                p.randomize()
                self.assertEqual(int(p.rf), s)
                self.assertTrue(10 < int(p.a) < 20)

    def test_state_change_between_solves(self):
        # Re-pointing the non-rand bounds changes the feasible window.
        p = Packet()
        p.state = 1
        p.foo.x = 100
        p.bar.y = 120
        for _ in range(10):
            p.randomize()
            self.assertTrue(100 < int(p.a) < 120)
