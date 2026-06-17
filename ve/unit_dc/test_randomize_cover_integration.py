'''
Integration: the full CRV loop in the dataclass front-end — randomize a RandClass,
then sample a Covergroup that covers it via a cg_arg read-through. Exercises both
subsystems (solve + coverage) together on the dv-solve backend.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestRandomizeCoverIntegration(DcTestCase):

    def test_randomize_then_cover(self):

        @vdc.dataclass
        class Txn(vdc.RandClass):
            op: vdc.u4 = vdc.rand()
            addr: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.op <= 3
                self.addr < 64

        @vdc.dataclass
        class TxnCov(vdc.Covergroup):
            txn: Txn = vdc.cg_arg()
            op_cp: vdc.Coverpoint[vdc.u4] = vdc.coverpoint(
                lambda s: s.txn.op, bins=dict(ops=vdc.bin_array([], [0, 3])))
            addr_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.txn.addr,
                bins=dict(lo=vdc.bin([0, 31]), hi=vdc.bin([32, 63])))

        t = Txn()
        cov = TxnCov(txn=t)

        for _ in range(200):
            t.randomize()
            # Constraints hold on every solution (independent oracle).
            self.assertLessEqual(t.op, 3)
            self.assertLess(t.addr, 64)
            cov.sample()
            if cov.get_coverage() == 100:
                break

        # op covered (4 bins over 0..3) and addr covered (lo/hi halves).
        self.assertEqual(cov.op_cp.get_coverage(), 100)
        self.assertEqual(cov.addr_cp.get_coverage(), 100)
        self.assertEqual(cov.get_coverage(), 100)

    def test_bin_array_duplicates(self):
        # SV §19.5.1: duplicate values are retained — value 1/4/7 hit both their
        # range bin and their explicit-value bin. bin_array([4], [1,10], 1, 4, 7)
        # distributes 13 values (1..10, 1, 4, 7) into 4 bins.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(fixed=vdc.bin_array([4], [1, 10], 1, 4, 7)))

        cg = my_cg()
        for v in (1, 4, 7, 10):
            cg.sample(v)
        # 4 bins, all reached -> 100% (the duplicate retention is what lets the
        # 13 values pack into exactly 4 bins the classic way).
        self.assertEqual(cg.a.get_coverage(), 100)
