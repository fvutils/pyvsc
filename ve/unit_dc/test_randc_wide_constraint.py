'''
Dataclass-front-end adaptation of t_randc_wide_constraint.v.

Wide randc fields with constraints must (a) not hang -- the cyclic machinery must
not enumerate the full 2**16 domain to make progress -- and (b) still cycle
correctly over a *small* constrained sub-domain. The classic test's fourth case (a
60-bit enum) is covered by test_randc_enum_constraint instead, since dc enum fields
use 32-bit storage and the wide-storage aspect does not survive the adaptation.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandcWideConstraint(DcTestCase):

    def test_wide_full_domain_no_hang(self):
        # RandcFull: a 16-bit randc with a trivially-true constraint. Drawing many
        # values must complete promptly and never repeat consecutively (the
        # exclusion list only ever holds the handful of values seen so far).
        @vdc.dataclass
        class my_c(vdc.RandClass):
            value: vdc.u16 = vdc.randc()

            @vdc.constraint
            def range_c(self):
                self.value >= 0

        c = my_c()
        c.randomize()
        last = int(c.value)
        for _ in range(100):
            c.randomize()
            cur = int(c.value)
            self.assertNotEqual(cur, last)
            last = cur

    def test_wide_small_constrained_domain_cycles(self):
        # RandcSmall: a 16-bit randc pinned to inside {[0:7]} cycles over exactly
        # those 8 values -- the UNSAT-reset closes each cycle at the constrained
        # domain, not the declared 16-bit one.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            value: vdc.u16 = vdc.randc()

            @vdc.constraint
            def range_c(self):
                self.value.inside(vdc.rangelist(vdc.rng(0, 7)))

        c = my_c()
        valid = list(range(0, 8))
        count = {v: 0 for v in valid}
        cycles = 3
        for _ in range(cycles):
            window = []
            for _ in range(len(valid)):
                c.randomize()
                self.assertIn(int(c.value), valid)
                window.append(int(c.value))
                count[int(c.value)] += 1
            self.assertEqual(sorted(window), valid)
        for v in valid:
            self.assertEqual(count[v], cycles)
