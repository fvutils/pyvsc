'''
Dataclass-front-end coverage report-model structure (parallel of the report-model
assertions in ve/unit/test_coverage_cross.py etc.).

vsc.get_coverage_report_model() reads the shared CoverageRegistry, so it reports dc
covergroups unchanged — this pins the report structure (coverpoint/cross counts and
their coverage numbers) the same way the classic suite does.
'''
from dc_test_case import DcTestCase
import vsc
import vsc.dc as vdc


class TestCoverageReport(DcTestCase):

    def test_report_model_structure(self):

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([2], (0, 3))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([2], (0, 3))))
            axb: vdc.Cross = vdc.cross(lambda s: s.a, lambda s: s.b)

        cg = my_cg()
        cg.sample(0, 0)     # a0,b0  -> cross (0,0)
        cg.sample(2, 2)     # a1,b1  -> cross (1,1)

        report = vsc.get_coverage_report_model()
        self.assertEqual(len(report.covergroups), 1)
        cg_r = report.covergroups[0]
        self.assertEqual(len(cg_r.coverpoints), 2)
        self.assertEqual(len(cg_r.crosses), 1)
        # Both coverpoints fully covered (both bins hit each).
        self.assertEqual(cg_r.coverpoints[0].coverage, 100)
        self.assertEqual(cg_r.coverpoints[1].coverage, 100)
        # Cross: 2 of 4 product bins hit -> 50%.
        self.assertEqual(cg_r.crosses[0].coverage, 50)
