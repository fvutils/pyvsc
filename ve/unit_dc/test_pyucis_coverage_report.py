'''
Dataclass-front-end parallel of ve/unit/test_pyucis_coverage_report.py (M4).

Because a vdc.Covergroup registers its CovergroupModel with the same
CoverageRegistry the classic front-end uses, the existing pyucis CoverageSaveVisitor
/ CoverageReportBuilder export works on dc covergroups unchanged — UCIS export comes
"for free" from reusing the SV-faithful model.
'''
from datetime import datetime

from ucis import UCIS_TESTSTATUS_OK
from ucis.mem.mem_factory import MemFactory
from ucis.report.coverage_report_builder import CoverageReportBuilder
from ucis.test_data import TestData

from dc_test_case import DcTestCase
from vsc.impl.coverage_registry import CoverageRegistry
from vsc.visitors.coverage_save_visitor import CoverageSaveVisitor
import vsc.dc as vdc


class TestPyUCISCoverageReport(DcTestCase):

    def get_ucis_report(self):
        covergroups = CoverageRegistry.inst().covergroup_types()
        db = MemFactory.create()
        cov_visitor = CoverageSaveVisitor(db)
        cov_visitor.save(
            TestData(
                UCIS_TESTSTATUS_OK,
                "UCIS:simulator",
                datetime.now().strftime("%Y%m%d%H%M%S")),
            covergroups)
        return CoverageReportBuilder.build(cov_visitor.db)

    def test_even_weights(self):
        # Mirrors classic test_even_weights: a_cp 4/8 bins, b_cp 4/4 bins,
        # equal weights -> 75% overall, exported through the UCIS writer.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a_arr=vdc.bin_array([], [1, 8])))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b_arr=vdc.bin_array([], [1, 4])))

        cg = my_cg()
        for i in range(1, 5):
            cg.sample(a=i)          # cover a in 1..4 (of 1..8)
        for i in range(1, 5):
            cg.sample(b=i)          # cover b in 1..4 (of 1..4)

        report = self.get_ucis_report()
        self.assertEqual(1, len(report.covergroups))
        self.assertEqual(75, report.coverage)
