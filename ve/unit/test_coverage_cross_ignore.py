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
from vsc.model.coverpoint_bin_enum_model import CoverpointBinEnumModel
from vsc.model.coverpoint_bin_single_bag_model import CoverpointBinSingleBagModel
from vsc.model.coverpoint_bin_single_range_model import CoverpointBinSingleRangeModel
from vsc.model.coverpoint_bin_single_val_model import CoverpointBinSingleValModel
from vsc.model.coverpoint_bin_single_wildcard_model import CoverpointBinSingleWildcardModel
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_ref_model import ExprRefModel
from vsc.model.rangelist_model import RangelistModel
from vsc.model.wildcard_binspec import WildcardBinspec


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


class TestCoverpointBinRange(VscTestCase):
    """``get_bin_range`` contract, which ``bin_info.intersect`` relies on: an
    iterable of entries, each an int or an ``(lo, hi)`` tuple."""

    def _check_entries(self, rng):
        self.assertIsInstance(rng, tuple)
        for e in rng:
            if isinstance(e, tuple):
                self.assertEqual(len(e), 2)
                self.assertTrue(all(isinstance(v, int) for v in e))
                self.assertLessEqual(e[0], e[1])
            else:
                self.assertIsInstance(e, int)

    def test_every_bin_model(self):
        models = [
            CoverpointBinSingleValModel("v", 5),
            CoverpointBinSingleRangeModel("r", 0, 63),
            CoverpointBinArrayModel("a", 0, 3),
            CoverpointBinEnumModel("e", 2),
            CoverpointBinSingleBagModel("b1", RangelistModel([(0, 63)])),
            CoverpointBinSingleBagModel("b2", RangelistModel([5])),
            CoverpointBinSingleBagModel("b3", RangelistModel([1, (4, 7), 9])),
            CoverpointBinSingleWildcardModel(
                "w", WildcardBinspec([(0x10, 0xF0)])),
        ]
        for m in models:
            with self.subTest(model=m.name):
                self._check_entries(m.get_bin_range(0))

    def test_bag_entries(self):
        self.assertEqual(
            CoverpointBinSingleBagModel("b", RangelistModel([(0, 63)]))
            .get_bin_range(0), ((0, 63),))
        self.assertEqual(
            CoverpointBinSingleBagModel("b", RangelistModel([5]))
            .get_bin_range(0), (5,))
        self.assertEqual(
            CoverpointBinSingleBagModel("b", RangelistModel([1, (4, 7)]))
            .get_bin_range(0), (1, (4, 7)))

    def test_bag_has_no_side_effect_on_binspec(self):
        spec = RangelistModel([(0, 63)])
        CoverpointBinSingleBagModel("b", spec).get_bin_range(0)
        self.assertEqual(spec.range_l, [[0, 63]])


class TestCoverageCrossIgnoreBinKinds(VscTestCase):
    """Cross selection over each kind of component bin. Bag bins (one
    ``vsc.bin(...)``) used to raise ``'RangelistModel' object is not
    iterable``."""

    def _bag_cp(self, name):
        # bin 0: [0..63]; bin 1: 100 or [200..210]
        return _cp_with_bins(
            name,
            CoverpointBinSingleBagModel(name + "_lo", RangelistModel([(0, 63)])),
            CoverpointBinSingleBagModel(
                name + "_mix", RangelistModel([100, (200, 210)])))

    def test_bag_single_range(self):
        a = self._bag_cp("a")
        b = self._bag_cp("b")
        x = _cross("axb", [a, b], {
            "c": lambda ba, bb: ba.intersect([(0, 10)])
            and bb.intersect([(0, 10)])})
        self.assertEqual(x.n_ignore, 1)
        self.assertFalse(x.get_bin_valid(0))

    def test_bag_point_entry(self):
        # 100 is a point entry of bin 1.
        a = self._bag_cp("a")
        b = self._bag_cp("b")
        x = _cross("axb", [a, b], {"c": lambda ba, bb: ba.intersect([100])})
        self.assertEqual(x.n_ignore, 2)          # a_mix row
        self.assertFalse(x.get_bin_valid(2))
        self.assertFalse(x.get_bin_valid(3))

    def test_bag_second_range_entry(self):
        a = self._bag_cp("a")
        b = self._bag_cp("b")
        x = _cross("axb", [a, b], {"c": lambda ba, bb: bb.intersect([(205, 300)])})
        self.assertEqual(x.n_ignore, 2)          # b_mix column
        self.assertFalse(x.get_bin_valid(1))
        self.assertFalse(x.get_bin_valid(3))

    def test_bag_gap_between_entries_selects_nothing(self):
        a = self._bag_cp("a")
        b = self._bag_cp("b")
        x = _cross("axb", [a, b], {
            "c": lambda ba, bb: ba.intersect([(64, 99), (101, 199), 211])})
        self.assertEqual(x.n_ignore, 0)

    def test_bag_boundaries(self):
        # Touching an end is an overlap; one past it is not.
        a = self._bag_cp("a")
        b = self._bag_cp("b")
        x = _cross("axb", [a, b], {"c": lambda ba, bb: ba.intersect([63])})
        self.assertEqual(x.n_ignore, 2)
        x = _cross("axb", [self._bag_cp("a"), self._bag_cp("b")],
                   {"c": lambda ba, bb: ba.intersect([64])})
        self.assertEqual(x.n_ignore, 0)

    def test_wildcard_bin(self):
        # 0x1? = [16..31]
        a = _cp_with_bins(
            "a",
            CoverpointBinSingleWildcardModel("a_1x", WildcardBinspec([(0x10, 0xF0)])),
            CoverpointBinSingleValModel("a_0", 0))
        b = self._array_cp_2()
        x = _cross("axb", [a, b], {"c": lambda ba, bb: ba.intersect([20])})
        self.assertEqual(x.n_ignore, 2)
        x = _cross("axb", [a, self._array_cp_2()],
                   {"c": lambda ba, bb: ba.intersect([(32, 255)])})
        self.assertEqual(x.n_ignore, 0)

    def test_enum_bin(self):
        a = _cp_with_bins("a", CoverpointBinEnumModel("A", 0),
                          CoverpointBinEnumModel("B", 1))
        x = _cross("axb", [a, self._array_cp_2()],
                   {"c": lambda ba, bb: ba.intersect([1])})
        self.assertEqual(x.n_ignore, 2)
        self.assertFalse(x.get_bin_valid(2))

    def _array_cp_2(self):
        return _cp_with_bins("b", CoverpointBinArrayModel("b", 0, 1))


class TestClassicCrossIgnoreBins(VscTestCase):
    """The classic front end: ``vsc.cross(ignore_bins=...)`` over
    ``vsc.bin`` components (bag bins)."""

    def _cg(self, ignore):
        import vsc

        @vsc.covergroup
        class cg_t(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t(), b=vsc.uint8_t()))
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    lo=vsc.bin((0, 63)), mix=vsc.bin(70, (200, 210))))
                self.cp_b = vsc.coverpoint(self.b, bins=dict(
                    b=vsc.bin_array([2], (0, 255))))
                self.cr = vsc.cross([self.cp_a, self.cp_b],
                                    ignore_bins=dict(x=ignore))
        return cg_t()

    def test_range_bin(self):
        cg = self._cg(lambda a, b: a.intersect([(0, 10)])
                      and b.intersect([(128, 255)]))
        m = cg.cr.model
        self.assertEqual(m.n_bins, 4)
        self.assertEqual(m.n_ignore, 1)
        self.assertFalse(m.get_bin_valid(1))

    def test_multi_entry_bin_and_coverage(self):
        cg = self._cg(lambda a, b: a.intersect([205]))
        m = cg.cr.model
        self.assertEqual(m.n_ignore, 2)
        cg.sample(5, 0)
        cg.sample(5, 200)
        self.assertEqual(cg.cr.get_coverage(), 100)
