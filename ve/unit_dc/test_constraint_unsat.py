'''
Dataclass-front-end adaptation of the Verilator UNSAT corpus (t_constraint_unsat.v).

Two flavours of infeasibility:
  - a class with legal range constraints (addr<127; 10<data<200) that an inline
    ``randomize_with`` pins to a value OUTSIDE the class range — the inline
    equality and the class constraint jointly have no solution (the SV `check`
    helper's `randomize() with { addr==a; data==d; }` calls);
  - a class whose own two constraints conflict (x>100 AND x<50) — plain
    ``randomize`` is UNSAT.

Every infeasible case must raise ``vdc.SolveFailure`` (Verilator's
``randomize()`` returning 0), and the feasible control must succeed.  Under
dv-solve this doubles as a primary-path UNSAT gate (a wrong SAT verdict here is
a soundness bug the SAT-model XCHECK cannot catch — cf.
ve/unit/test_dvsolve_unsat_parity.py).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


# --- Packet: legal ranges, inline equality may fall outside them ------------
@vdc.dataclass
class Packet(vdc.RandClass):
    addr: vdc.u8 = vdc.rand()
    data: vdc.u8 = vdc.rand()

    @vdc.constraint
    def addr_range(self):
        self.addr < 127

    @vdc.constraint
    def data_range(self):
        self.data > 10
        self.data < 200


# --- TestConflict: the class's own two constraints contradict ---------------
@vdc.dataclass
class Conflict(vdc.RandClass):
    x: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c1(self):
        self.x > 100

    @vdc.constraint
    def c2(self):
        self.x < 50


class TestConstraintUnsat(DcTestCase):

    def _check(self, addr, data):
        """Mirror Packet::check — randomize pinning addr==a, data==d.

        Returns True if the joint problem is satisfiable, False on SolveFailure.
        """
        pkt = Packet()
        try:
            with pkt.randomize_with() as it:
                it.addr == addr
                it.data == data
            return True
        except vdc.SolveFailure:
            return False

    def test_valid(self):
        # Test 1: both inside the class ranges -> SAT, and the pins take effect.
        pkt = Packet()
        with pkt.randomize_with() as it:
            it.addr == 50
            it.data == 100
        self.assertEqual(int(pkt.addr), 50)
        self.assertEqual(int(pkt.data), 100)

    def test_addr_out_of_range(self):
        # Test 2: addr==128 violates addr<127.
        self.assertFalse(self._check(128, 18))

    def test_data_too_small(self):
        # Test 3: data==5 violates data>10.
        self.assertFalse(self._check(100, 5))

    def test_data_too_large(self):
        # Test 4: data==250 violates data<200.
        self.assertFalse(self._check(100, 250))

    def test_both_violated(self):
        # Test 5: addr==200 and data==5 both out of range.
        self.assertFalse(self._check(200, 5))

    def test_conflicting_class_constraints(self):
        # Test 6: x>100 AND x<50 has no solution under plain randomize.
        tc = Conflict()
        with self.assertRaises(vdc.SolveFailure):
            tc.randomize()

    def test_feasible_still_varies(self):
        # Sanity: with no inline pins the class ranges are wide and both vary.
        pkt = Packet()
        seen_a, seen_d = set(), set()
        for _ in range(30):
            pkt.randomize()
            self.assertLess(int(pkt.addr), 127)
            self.assertTrue(10 < int(pkt.data) < 200)
            seen_a.add(int(pkt.addr))
            seen_d.add(int(pkt.data))
        self.assertGreater(len(seen_a), 1)
        self.assertGreater(len(seen_d), 1)
