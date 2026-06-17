'''
Dataclass-front-end parallel of ve/unit/test_coverage_igore_bins.py (sic).

Ports the enum auto-bin exclude scenarios — `ignore_bins` and `illegal_bins` on an
enum coverpoint. `illegal_bins` was the genuine dc coverage gap (no prior dc twin
exercised it). Both exclude their values from the coverage denominator and track a
hit count in the shared coverage report model (read via `vsc.get_coverage_report_model`,
which reports dc covergroups too); neither raises on a hit — matching the legacy
front-end. The scalar pull-coverpoint / part-select cases in the classic file use
legacy `with_sample` + `instr.value[7:5]` idioms and are covered by the
push/pull/part-select dc tests elsewhere.
'''
from enum import IntEnum, auto

from dc_test_case import DcTestCase
import vsc
import vsc.dc as vdc


class my_e(IntEnum):
    A = auto()
    B = auto()
    C = auto()
    D = auto()
    E = auto()
    F = auto()
    G = auto()
    H = auto()


class TestCoverageIgnoreBins(DcTestCase):

    def test_enum_bins_autobin_exclude(self):
        # Auto bin per enumerator (8), minus two ignore_bins -> 6 active bins.

        @vdc.dataclass
        class val_cg(vdc.Covergroup):
            cp_v: vdc.Coverpoint[my_e] = vdc.coverpoint(ignore_bins=dict(
                ignore_1=vdc.bin(my_e.D),
                ignore_2=vdc.bin(my_e.H)))

        cg = val_cg()
        for v in (my_e.A, my_e.B, my_e.C, my_e.E, my_e.F, my_e.G):
            cg.sample(v)

        m = vsc.get_coverage_report_model()
        self.assertEqual(len(m.covergroups), 1)
        self.assertEqual(len(m.covergroups[0].coverpoints), 1)
        cp = m.covergroups[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 6)
        self.assertEqual(len(cp.ignore_bins), 2)
        self.assertEqual(cp.ignore_bins[0].count, 0)
        self.assertEqual(cp.ignore_bins[1].count, 0)
        # all 6 active bins hit
        self.assertEqual(cg.cp_v.get_coverage(), 100)

        cg.sample(my_e.D)
        cp = vsc.get_coverage_report_model().covergroups[0].coverpoints[0]
        self.assertEqual(cp.ignore_bins[0].count, 1)
        self.assertEqual(cp.ignore_bins[1].count, 0)

        cg.sample(my_e.H)
        cp = vsc.get_coverage_report_model().covergroups[0].coverpoints[0]
        self.assertEqual(cp.ignore_bins[0].count, 1)
        self.assertEqual(cp.ignore_bins[1].count, 1)
        # ignored hits don't change coverage
        self.assertEqual(cg.cp_v.get_coverage(), 100)

    def test_enum_bins_autobin_exclude_illegal(self):
        # 8 enumerators - 1 ignore (D) - 1 illegal (H) -> 6 active bins.

        @vdc.dataclass
        class val_cg(vdc.Covergroup):
            cp_v: vdc.Coverpoint[my_e] = vdc.coverpoint(
                ignore_bins=dict(ignore_1=vdc.bin(my_e.D)),
                illegal_bins=dict(ignore_2=vdc.bin(my_e.H)))

        cg = val_cg()
        for v in (my_e.A, my_e.B, my_e.C, my_e.E, my_e.F, my_e.G):
            cg.sample(v)

        m = vsc.get_coverage_report_model()
        self.assertEqual(len(m.covergroups), 1)
        cp = m.covergroups[0].coverpoints[0]
        self.assertEqual(len(cp.bins), 6)
        self.assertEqual(len(cp.ignore_bins), 1)
        self.assertEqual(len(cp.illegal_bins), 1)
        self.assertEqual(cp.ignore_bins[0].count, 0)
        self.assertEqual(cp.illegal_bins[0].count, 0)
        self.assertEqual(cg.cp_v.get_coverage(), 100)

        cg.sample(my_e.D)
        cp = vsc.get_coverage_report_model().covergroups[0].coverpoints[0]
        self.assertEqual(cp.ignore_bins[0].count, 1)
        self.assertEqual(cp.illegal_bins[0].count, 0)

        cg.sample(my_e.H)   # illegal hit: tracked, not raised
        cp = vsc.get_coverage_report_model().covergroups[0].coverpoints[0]
        self.assertEqual(cp.ignore_bins[0].count, 1)
        self.assertEqual(cp.illegal_bins[0].count, 1)
        self.assertEqual(cg.cp_v.get_coverage(), 100)
