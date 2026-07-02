'''
Dataclass-front-end adaptation of Verilator ve/test_regress/t/t_randc.v.

Exercises ``vdc.randc()`` cyclic randomization (IEEE 1800 §18.4.2): a randc field
iterates over every value in its domain in a random order, repeating none until the
domain is exhausted, then begins a fresh permutation. The defining invariant the
classic test checks is *uniformity over complete cycles* -- over N full cycles each
domain value appears exactly N times -- plus, for wider fields, no value repeats on
consecutive draws.

randc cyclic semantics are implemented in vsc/dc/cyclic.py (per-instance value
exclusion with UNSAT/size reset), backend-agnostic across dv-solve and boolector.
'''
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandc(DcTestCase):

    def test_narrow_full_domain_uniform(self):
        # ClsNarrow: a small randc covers its whole 0..2**W-1 domain each cycle;
        # over N complete cycles every value appears exactly N times.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u2 = vdc.randc()   # 2-bit: domain {0,1,2,3}

        c = my_c()
        cycles = 10
        domain = [0, 1, 2, 3]
        count = {v: 0 for v in domain}
        for _ in range(cycles):
            window = []
            for _ in range(len(domain)):
                c.randomize()
                window.append(int(c.x))
                count[int(c.x)] += 1
            # No repeat within a single cycle.
            self.assertEqual(sorted(window), domain)
        # Uniform over all complete cycles.
        for v in domain:
            self.assertEqual(count[v], cycles)

    def test_wide_no_consecutive_repeat(self):
        # ClsWide: a wider randc must not return the same value twice in a row
        # (the next draw is always a not-yet-used value from the current cycle).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: vdc.u16 = vdc.randc()

        c = my_c()
        c.randomize()
        last = int(c.x)
        for _ in range(50):
            c.randomize()
            cur = int(c.x)
            self.assertNotEqual(cur, last)
            last = cur

    def test_enum_cyclic(self):
        # ClsEnum: randc over an enum cycles through exactly its members.
        class enum_t(IntEnum):
            TWO = 2
            FIVE = 5
            SIX = 6

        @vdc.dataclass
        class my_c(vdc.RandClass):
            x: enum_t = vdc.randc()

        c = my_c()
        members = sorted(int(m) for m in enum_t)
        count = {v: 0 for v in members}
        cycles = 10
        for _ in range(cycles):
            window = []
            for _ in range(len(members)):
                c.randomize()
                self.assertIn(int(c.x), members)
                window.append(int(c.x))
                count[int(c.x)] += 1
            self.assertEqual(sorted(window), members)
        for v in members:
            self.assertEqual(count[v], cycles)
