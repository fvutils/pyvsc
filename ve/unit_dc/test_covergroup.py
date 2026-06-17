'''
Dataclass-front-end parallel of ve/unit coverage tests (Phase 3, slice 1).

Push/pull coverpoints with explicit + auto + enum bins, delegating to pyvsc's
IEEE-1800 coverage model. The coverage numbers asserted here match the classic
front-end's (test_coverpoint_bins.py): same bins, same SV computation.
'''
from enum import Enum, auto

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestCovergroup(DcTestCase):

    def test_push_explicit_bins(self):
        # bin_array([4], (0,16)) -> 4 uniform bins over 0..16. Classic asserts
        # 25% after hitting bin 0, 50% after also hitting bin 1.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a1=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0)
        cg.sample(3)
        self.assertEqual(cg.a.get_coverage(), 25)
        cg.sample(4)
        cg.sample(7)
        self.assertEqual(cg.a.get_coverage(), 50)
        self.assertEqual(cg.get_coverage(), 50)

    def test_push_named_bins(self):
        # Two named single bins; hitting one covers 50%.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u4] = vdc.coverpoint(bins={
                "lo": vdc.bin(1, 2, 4),
                "hi": vdc.bin(8, [12, 15]),
            })

        cg = my_cg()
        cg.sample(1)
        self.assertEqual(cg.a.get_coverage(), 50)
        cg.sample(13)
        self.assertEqual(cg.a.get_coverage(), 100)

    def test_enum_auto_bins(self):
        # One auto bin per enumerator (SV 19.5.3). Classic asserts 50 then 100.

        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[my_e] = vdc.coverpoint()

        cg = my_cg()
        cg.sample(my_e.A)
        cg.sample(my_e.C)
        self.assertEqual(cg.a.get_coverage(), 50)
        cg.sample(my_e.D)
        cg.sample(my_e.B)
        self.assertEqual(cg.a.get_coverage(), 100)

    def test_pull_coverpoint(self):
        # A pull coverpoint reads a sample_arg field via its ref lambda.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            x: vdc.u8 = vdc.sample_arg()
            x_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.x, bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0)        # x = 0 -> bin 0
        cg.sample(7)        # x = 7 -> bin 1
        self.assertEqual(cg.x_cp.get_coverage(), 50)

    def test_cross(self):
        # Cross of two 2-bin coverpoints -> 4 cross bins. Coverage is
        # covered_cross_bins / 4 (SV 19.11.2).

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([2], (0, 3))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([2], (0, 3))))
            axb: vdc.Cross = vdc.cross(lambda s: s.a, lambda s: s.b)

        cg = my_cg()
        cg.sample(0, 0)                       # (a0, b0)
        self.assertEqual(cg.axb.get_coverage(), 25)
        cg.sample(0, 2)                       # (a0, b1)
        cg.sample(2, 0)                       # (a1, b0)
        cg.sample(2, 2)                       # (a1, b1)
        self.assertEqual(cg.axb.get_coverage(), 100)

    def test_ignore_bins_left_trim(self):
        # Ignored values are removed *before* bin partitioning (SV §19.5.5).
        # bin_array([4], [1,3],[4,6],[7,9],[10,12]) over 11 values, ignore {4},
        # repartitions 11 values into 4 bins: [1,2],[3,5],[6,7],[8,12].
        # Mirrors classic test_ignore_left_trim.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(rng_1=vdc.bin_array([4], [1, 3], [4, 6], [7, 9], [10, 12])),
                ignore_bins=dict(invalid=vdc.bin(4)))

        cg = my_cg()
        cg.sample(2)
        cg.sample(5)
        cg.sample(6)
        cg.sample(12)
        self.assertEqual(cg.a.get_bin_hits(0), 1)   # [1,2]
        self.assertEqual(cg.a.get_bin_hits(1), 1)   # [3,5]
        self.assertEqual(cg.a.get_bin_hits(2), 1)   # [6,7]
        self.assertEqual(cg.a.get_bin_hits(3), 1)   # [8,12]
        self.assertEqual(cg.a.get_coverage(), 100)

    def test_wildcard_bin(self):
        # wildcard_bin("0x8x") matches 0x80..0x8F (SV §19.5.4).

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.wildcard_bin("0x8x")))

        cg = my_cg()
        cg.sample(0)
        self.assertEqual(cg.get_coverage(), 0.0)
        cg.sample(0x81)
        self.assertEqual(cg.a.get_coverage(), 100.0)

    def test_iff_guard(self):
        # An iff guard disables sampling when false (SV §19.5).

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            en: vdc.u8 = vdc.sample_arg()
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                iff=lambda s: s.en != 0,
                bins=dict(a=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0, 0)     # a=0, en=0 -> guard false, not counted
        self.assertEqual(cg.a.get_coverage(), 0)
        cg.sample(0, 1)     # a=0, en=1 -> guard true, bin 0 hit
        self.assertEqual(cg.a.get_coverage(), 25)

    def test_cg_arg_read_through(self):
        # cg_arg binds an external object at construction; a pull coverpoint
        # navigates into it.

        @vdc.dataclass
        class Txn(vdc.RandClass):
            op: vdc.u4 = vdc.rand()

        @vdc.dataclass
        class Cov(vdc.Covergroup):
            txn: Txn = vdc.cg_arg()
            op_cp: vdc.Coverpoint[vdc.u4] = vdc.coverpoint(
                lambda s: s.txn.op,
                bins=dict(lo=vdc.bin(0, 1), hi=vdc.bin(2, 3)))

        t = Txn()
        cov = Cov(txn=t)
        t.op = 0
        cov.sample()
        self.assertEqual(cov.op_cp.get_coverage(), 50)
        t.op = 3
        cov.sample()
        self.assertEqual(cov.op_cp.get_coverage(), 100)

    def test_enum_cross(self):
        # Cross of two enum coverpoints (2x2 -> 4 cross bins). Sampling the
        # diagonal covers 2/4 = 50%. Mirrors classic test_coverage_cross.

        class e1(Enum):
            A = 0
            B = auto()

        class e2(Enum):
            X = 0
            Y = auto()

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            p: vdc.Coverpoint[e1] = vdc.coverpoint()
            q: vdc.Coverpoint[e2] = vdc.coverpoint()
            pq: vdc.Cross = vdc.cross(lambda s: s.p, lambda s: s.q)

        cg = my_cg()
        cg.sample(e1.A, e2.X)
        cg.sample(e1.B, e2.Y)
        self.assertEqual(cg.p.get_coverage(), 100)
        self.assertEqual(cg.q.get_coverage(), 100)
        self.assertEqual(cg.pq.get_coverage(), 50)

    def test_nested_cross(self):
        # A cross whose target is another cross flattens to its component
        # coverpoints (SV-style): abc = cross(ab, c) -> 3 coverpoints a,b,c,
        # 2 bins each -> 8 cross bins; one combo -> 12.5%.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(x=vdc.bin_array([2], (0, 3))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(x=vdc.bin_array([2], (0, 3))))
            c: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(x=vdc.bin_array([2], (0, 3))))
            ab: vdc.Cross = vdc.cross(lambda s: s.a, lambda s: s.b)
            abc: vdc.Cross = vdc.cross(lambda s: s.ab, lambda s: s.c)

        cg = my_cg()
        cg.sample(0, 0, 0)
        self.assertEqual(cg.abc.get_coverage(), 12.5)

    def test_options_auto_bin_max(self):
        # option.auto_bin_max caps the number of auto bins (SV §19.5.3): an 8-bit
        # coverpoint with auto_bin_max=4 has 4 bins; one value -> 25%.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(options=dict(auto_bin_max=4))

        cg = my_cg()
        cg.sample(0)
        self.assertEqual(cg.a.get_coverage(), 25)

    def test_type_aggregation(self):
        # get_coverage() is cumulative across instances (SV §19.11.3): two
        # instances each hitting a different bin -> type coverage 100, inst 50.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([2], (0, 7))))

        cg1 = my_cg()
        cg2 = my_cg()
        cg1.sample(0)       # bin 0
        cg2.sample(4)       # bin 1
        self.assertEqual(cg1.get_inst_coverage(), 50)
        self.assertEqual(cg2.get_inst_coverage(), 50)
        # Cumulative (type) coverage is the union across both instances.
        self.assertEqual(cg1.get_coverage(), 100)
        self.assertEqual(cg2.get_coverage(), 100)

    def test_two_coverpoints_avg(self):
        # Covergroup coverage is the average of its coverpoints.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0, 0)     # a -> 25%, b -> 25%
        self.assertEqual(cg.a.get_coverage(), 25)
        self.assertEqual(cg.b.get_coverage(), 25)
        self.assertEqual(cg.get_coverage(), 25)
        cg.sample(4, 0)     # a -> 50%, b still 25%
        self.assertEqual(cg.get_coverage(), 37.5)
