'''
Dataclass-front-end adaptation of t_constraint_implication_set.v (IEEE 1800-2023
18.7.2): the many RHS *shapes* allowed on the right of the implication operator
``->``.  A single rand ``mode`` selects which implication is live; the rest have
false antecedents and are vacuous.  Each ``constraint`` maps to one
``with vdc.implies(mode == k):`` block whose body is a different shape:

  - bare expression                (mode 0: b == 9)
  - gated block (inner if)          (mode 1: txn==READ -> low nibble of addr 0)
  - multi-statement block           (mode 2: two part-selects of address)
  - bare if                         (mode 3: a==1 -> b==7)
  - if/else                         (mode 4: a==1 ? b==0xa : b==0xb)
  - foreach                         (mode 5: every arr[i] < 0x40)
  - unique                          (mode 6: uarr elements distinct)
  - soft                            (mode 7: soft b==0xd)
  - nested implication              (mode 8: a==0 -> b==5)

The ``disable soft`` cases from the SV source are dropped — that meta-level
directive has no dc front-end equivalent.  ``address % (1<<4) == 0`` (low nibble
zero) is expressed as the equivalent part-select ``address[3:0] == 0``.
'''
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class txn_e(IntEnum):
    TXN_READ = 0
    TXN_WRITE = 1


@vdc.dataclass
class Forms(vdc.RandClass):
    mode: vdc.u4 = vdc.rand()
    a: vdc.u4 = vdc.rand()
    b: vdc.u4 = vdc.rand()
    c: vdc.u4 = vdc.rand()
    address: vdc.u32 = vdc.rand()
    txn_type: txn_e = vdc.rand()
    arr: list[vdc.u8] = vdc.rand(size=4)
    uarr: list[vdc.u4] = vdc.rand(size=3)

    @vdc.constraint
    def c_expr(self):
        with vdc.implies(self.mode == 0):
            self.b == 0x9

    @vdc.constraint
    def c_brace_gated(self):
        with vdc.implies(self.mode == 1):
            with vdc.if_then(self.txn_type == txn_e.TXN_READ):
                self.address[3:0] == 0        # address % 16 == 0

    @vdc.constraint
    def c_brace_multi(self):
        with vdc.implies(self.mode == 2):
            self.address[0] == 0
            self.address[31] == 0

    @vdc.constraint
    def c_if(self):
        with vdc.implies(self.mode == 3):
            with vdc.if_then(self.a == 1):
                self.b == 0x7

    @vdc.constraint
    def c_if_else(self):
        with vdc.implies(self.mode == 4):
            with vdc.if_then(self.a == 1):
                self.b == 0xa
            with vdc.else_then():
                self.b == 0xb

    @vdc.constraint
    def c_foreach(self):
        with vdc.implies(self.mode == 5):
            with vdc.foreach(self.arr) as it:
                it < 0x40

    @vdc.constraint
    def c_unique(self):
        with vdc.implies(self.mode == 6):
            vdc.unique(self.uarr[0], self.uarr[1], self.uarr[2])

    @vdc.constraint
    def c_soft(self):
        with vdc.implies(self.mode == 7):
            vdc.soft(self.b == 0xd)

    @vdc.constraint
    def c_nested(self):
        with vdc.implies(self.mode == 8):
            with vdc.implies(self.a == 0):
                self.b == 0x5


class TestImplicationSet(DcTestCase):

    def setUp(self):
        super().setUp()
        self.obj = Forms()

    def _run(self, n=10, **pins):
        """randomize_with pinning the given fields to constants; yield each draw."""
        for _ in range(n):
            with self.obj.randomize_with() as it:
                for name, val in pins.items():
                    getattr(it, name) == val
            yield self.obj

    def test_bare_expr(self):
        for o in self._run(mode=0):
            self.assertEqual(int(o.b), 0x9)

    def test_gated_block(self):
        for o in self._run(mode=1, txn_type=txn_e.TXN_READ):
            self.assertEqual(int(o.address) & 0xF, 0)

    def test_multi_statement_block(self):
        for o in self._run(mode=2):
            self.assertEqual(int(o.address) & 1, 0)
            self.assertEqual((int(o.address) >> 31) & 1, 0)

    def test_bare_if(self):
        for o in self._run(mode=3, a=1):
            self.assertEqual(int(o.b), 0x7)

    def test_if_else_then(self):
        for o in self._run(mode=4, a=1):
            self.assertEqual(int(o.b), 0xa)
        for o in self._run(mode=4, a=2):
            self.assertEqual(int(o.b), 0xb)

    def test_foreach(self):
        for o in self._run(mode=5):
            for e in o.arr:
                self.assertLess(int(e), 0x40)

    def test_unique(self):
        for o in self._run(mode=6):
            u = [int(o.uarr[i]) for i in range(3)]
            self.assertEqual(len(set(u)), 3, "uarr not unique: %s" % u)

    def test_soft(self):
        for o in self._run(mode=7):
            self.assertEqual(int(o.b), 0xd)      # nothing else binds b

    def test_nested_implication(self):
        for o in self._run(mode=8, a=0):
            self.assertEqual(int(o.b), 0x5)

    def test_antecedent_false_is_vacuous(self):
        # mode==9 activates no implication; b ranges freely over its 4 bits.
        seen = set()
        for o in self._run(n=40, mode=9):
            seen.add(int(o.b))
        self.assertGreater(len(seen), 1, "b should be free when no mode matches")
