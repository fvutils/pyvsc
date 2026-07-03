'''
Dataclass-front-end adaptation of t_constraint_cond.v.

The SV source is a ternary RHS gated by an ``if``:

    constraint q { if (i) { ((d == 0) ? y == 0 : 1'b1); } }

i.e. "when i is set and d==0, y must be 0; otherwise y is free".  The dc
front-end has no ternary (``?:``) constraint expression, so the equivalent
``cond ? a : true`` is expressed as a nested ``if_then`` (the false arm ``1'b1``
is just the absence of an else).  Two variants pin the non-rand guard ``d`` to 0
(inner arm live) and to 1 (inner arm vacuous, y free even when i==1), covering
both legs of the original ternary.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class Cls(vdc.RandClass):
    d: vdc.s32 = 0                    # non-rand guard (SV: plain int d)
    y: vdc.s32 = vdc.rand()
    i: vdc.u1 = vdc.rand()

    @vdc.constraint
    def q(self):
        with vdc.if_then(self.i == 1):
            with vdc.if_then(self.d == 0):     # ternary true-arm: y==0
                self.y == 0
            # ternary false-arm (1'b1) => no constraint


@vdc.dataclass
class ClsDNonZero(vdc.RandClass):
    d: vdc.s32 = 1                    # d!=0 => inner arm always vacuous
    y: vdc.s32 = vdc.rand()
    i: vdc.u1 = vdc.rand()

    @vdc.constraint
    def q(self):
        with vdc.if_then(self.i == 1):
            with vdc.if_then(self.d == 0):
                self.y == 0


class TestConstraintCond(DcTestCase):

    def test_cond_holds_and_y_varies(self):
        # Mirrors `check_rand`: every draw i==0 || y==0, and y takes >1 value.
        cls = Cls()
        seen_y = set()
        saw_i0, saw_i1 = False, False
        for _ in range(40):
            cls.randomize()
            self.assertTrue(int(cls.i) == 0 or int(cls.y) == 0,
                            "cond violated: i=%d y=%d" % (cls.i, cls.y))
            if int(cls.i) == 1:
                self.assertEqual(int(cls.y), 0)   # true-arm forces y==0
                saw_i1 = True
            else:
                saw_i0 = True
            seen_y.add(int(cls.y))
        self.assertGreater(len(seen_y), 1, "y never varied")
        self.assertTrue(saw_i0 and saw_i1, "did not exercise both i legs")

    def test_false_arm_leaves_y_free(self):
        # d==1 => the (d==0? ...) inner never fires; y is free even when i==1.
        cls = ClsDNonZero()
        seen_when_i1 = set()
        for _ in range(60):
            cls.randomize()
            if int(cls.i) == 1:
                seen_when_i1.add(int(cls.y))
        self.assertGreater(
            len(seen_when_i1), 1,
            "y should be unconstrained when d!=0 even with i==1")
