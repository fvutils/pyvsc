'''
Regression lock for the cross-ignore evaluation path in CoverpointCrossModel
(`_build_ignore_map` / `bin_info.intersect`). This path was dead/untested while
``binsof`` was a stub and crashed on range bins (`r[0][0]` indexed one level too
deep into the get_bin_range entry); value-bin intersect against `(lo,hi)` value
sets was also wrong. These tests exercise the model directly (shared-model level)
so the fix can't silently regress regardless of the dc front-end.
'''
from vsc_test_case import VscTestCase

from vsc.model.coverage_options_model import CoverageOptionsModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_single_range_model import CoverpointBinSingleRangeModel
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_ref_model import ExprRefModel


def _cp_with_bins(name, *bins):
    cp = CoverpointModel(ExprRefModel(lambda: 0, 8, False), name,
                         CoverageOptionsModel(), None)
    for b in bins:
        cp.add_bin_model(b)
    cp.finalize()
    return cp


def _cross(name, cps, ignore_bins):
    x = CoverpointCrossModel(name, CoverageOptionsModel(), None, ignore_bins)
    for cp in cps:
        x.add_coverpoint(cp)
    x.finalize()
    return x


class TestCoverageCrossIgnore(VscTestCase):

    def _range_cp(self, name):
        return _cp_with_bins(
            name,
            CoverpointBinSingleRangeModel(name + "_lo", 0, 63),
            CoverpointBinSingleRangeModel(name + "_hi", 192, 255))

    def _array_cp(self, name):
        # 4 value bins: 0,1,2,3
        return _cp_with_bins(name, CoverpointBinArrayModel(name, 0, 3))

    def test_range_bin_intersect_no_crash_and_correct(self):
        # The previously-crashing case: 2x2 cross of range-bin coverpoints,
        # ignore where a in [0..63] AND b in [192..255] -> exactly one cross bin.
        a = self._range_cp("a")
        b = self._range_cp("b")
        x = _cross("axb", [a, b], {
            "corner": lambda ba, bb: ba.intersect([(0, 63)])
            and bb.intersect([(192, 255)])})
        self.assertEqual(x.n_bins, 4)
        self.assertEqual(x.n_ignore, 1)
        # The ignored cross bin is <a_lo, b_hi> = idx 1 (a_lo=0, b_hi=1).
        self.assertFalse(x.get_bin_valid(1))
        for idx in (0, 2, 3):
            self.assertTrue(x.get_bin_valid(idx))

    def test_value_bin_intersect_point_and_range(self):
        # 4x4 array-bin cross. Ignore where a == 1 AND b in {2,3}: 1 row x 2 cols.
        a = self._array_cp("a")
        b = self._array_cp("b")
        x = _cross("axb", [a, b], {
            "x": lambda ba, bb: ba.intersect([1]) and bb.intersect([(2, 3)])})
        self.assertEqual(x.n_bins, 16)
        self.assertEqual(x.n_ignore, 2)
        # tuple order is (a_bin, b_bin); idx = a_bin*4 + b_bin. a==1 -> a_bin 1;
        # b in {2,3} -> b_bin 2,3 -> idx 6,7.
        self.assertFalse(x.get_bin_valid(6))
        self.assertFalse(x.get_bin_valid(7))
        self.assertTrue(x.get_bin_valid(5))

    def test_whole_coverpoint_predicate(self):
        # A predicate that selects an entire component (no intersect narrowing):
        # ignore every cross bin where a is in its first bin.
        a = self._array_cp("a")
        b = self._array_cp("b")
        x = _cross("axb", [a, b], {"row0": lambda ba, bb: ba.idx == 0})
        self.assertEqual(x.n_ignore, 4)   # whole b-row for a_bin 0
