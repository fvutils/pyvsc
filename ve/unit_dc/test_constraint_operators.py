'''
Dataclass-front-end adaptation of t_constraint_operators.v — the arithmetic,
bitwise, shift, relational and logical operators usable in a `@vdc.constraint`.

The dc constraint grammar supports ``+ - * // % & | ^ ~ << >>`` and the six
relational/equality ops; logical combination is spelled with ``&``/``|`` on
sub-comparisons (SV ``&&``/``||``) and negation with ``~``.  DROPPED from the SV
source (no dc-grammar / model equivalent, per the Tier-3 caveats):
  - the power operator ``**`` (all c_power* constraints);
  - concatenation ``{c, b}`` and width casts ``s64'(x)`` / ``u64'(tiny)``;
  - the ternary ``(cond ? a : b)`` (dc has no ``?:`` — cf. test_constraint_cond);
  - arithmetic shift-right ``>>>`` (only logical ``>>`` exists) and unary minus
    of a non-constant expression (``-~c`` — USub is const-only in the parser).

A regression fix rode in with this suite: ``ExprUnaryModel.is_signed()`` was
unimplemented, so any binary op with a ``~x`` operand (e.g. ``~c != 0x22``) threw
on BOTH back-ends; it now delegates to the operand's signedness.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class Operators(vdc.RandClass):
    x: vdc.s32 = vdc.rand()
    y: vdc.s32 = vdc.rand()
    z: vdc.s32 = vdc.rand()
    b: vdc.u32 = vdc.rand()
    c: vdc.u32 = vdc.rand()
    d: vdc.u32 = vdc.rand()
    tiny: vdc.u1 = vdc.rand()
    zero: vdc.u1 = vdc.rand()
    one: vdc.u1 = vdc.rand()

    # arithmetic identity (trivially true, exercises + and -)
    @vdc.constraint
    def arith(self):
        self.x + self.x - self.x == self.x

    # integer division and modulo
    @vdc.constraint
    def divmod(self):
        (self.x % 5) // 2 != (self.b % 99) // 7

    # multiplication
    @vdc.constraint
    def mul(self):
        self.x * 9 != self.b * 3

    # signed multiply pinning negatives: y*y==4,0<y<4 => y==2; z*z==4,-4<z<0 => z==-2
    @vdc.constraint
    def mul_signed(self):
        self.y * self.y == 4
        self.y > 0
        self.y < 4
        self.z * self.z == 4
        self.z < 0
        self.z > -4

    # implication with the -> operator
    @vdc.constraint
    def impl(self):
        with vdc.implies(self.tiny == 1):
            self.x != 10

    # bitwise NOT ( -~c in SV becomes ~c here; unary minus of an expr is unsupported )
    @vdc.constraint
    def unary(self):
        (~self.c) != 0x22

    # shift + xor/and/or logical mask (>>>' dropped -> '>>')
    @vdc.constraint
    def log(self):
        ((self.b ^ self.c) & (self.b >> 1 | self.b << 1 | self.c >> 2)) >= 0

    # relational chain via | (SV ||): x<=x always holds -> whole thing true
    @vdc.constraint
    def cmps(self):
        (self.x < self.x) | (self.x <= self.x) | \
            (self.x > self.x) | (self.x >= self.x)

    # constant pins
    @vdc.constraint
    def consts(self):
        self.zero == 0
        self.one == 1

    # part-select equality
    @vdc.constraint
    def sel(self):
        self.d[15:8] == 0x55


class TestConstraintOperators(DcTestCase):

    def test_deterministic_operator_outcomes(self):
        o = Operators()
        seen_x = set()
        for _ in range(30):
            o.randomize()
            # signed multiply
            self.assertEqual(int(o.y), 2)
            self.assertEqual(int(o.z), -2)
            # constants
            self.assertEqual(int(o.zero), 0)
            self.assertEqual(int(o.one), 1)
            # part-select
            self.assertEqual((int(o.d) >> 8) & 0xFF, 0x55)
            # bitwise-not inequality
            self.assertNotEqual((~int(o.c)) & 0xFFFFFFFF, 0x22)
            # (divmod / mul relations are `!=` constraints over signed x; the
            # solver enforces them under SV/C truncated-arithmetic semantics,
            # which differ from Python's floor mod/div — not re-checked here to
            # avoid a semantics mismatch. Their role is to exercise // % and *.)
            # implication: tiny==1 => x!=10
            if int(o.tiny) == 1:
                self.assertNotEqual(int(o.x), 10)
            seen_x.add(int(o.x))
        self.assertGreater(len(seen_x), 1, "x never varied")

    def test_implication_both_branches(self):
        # Force tiny both ways via randomize_with and confirm the guard.
        o = Operators()
        for _ in range(20):
            with o.randomize_with() as it:
                it.tiny == 1
            self.assertNotEqual(int(o.x), 10)
        saw = set()
        for _ in range(20):
            with o.randomize_with() as it:
                it.tiny == 0
            saw.add(int(o.x))
        # With tiny==0 the guard is off; x may (and should) range freely, incl 10-reachable.
        self.assertGreater(len(saw), 1)
