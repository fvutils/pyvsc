'''
binsof cross-bin selection (design §2 / impl plan BS): a cross ``ignore_bins`` /
``illegal_bins`` value is ``{name: lambda s: <binsof expr>}``. ``binsof(s.cp)``
selects a component coverpoint (whole, or narrowed with ``.intersect([...])``);
``& | ~`` combine selections (SV-1800 §19.6). Matched cross bins are excluded from
coverage. Coverage numbers are hand-computed against the small crosses.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


def _grid_cg(**cross_kwargs):
    # Two u8 coverpoints, 4 uniform bins each (0-63,64-127,128-191,192-255) -> a
    # 4x4 = 16-bin cross. A bin index k is the value k*64.
    @vdc.dataclass
    class my_cg(vdc.Covergroup):
        a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
            bins=dict(a=vdc.bin_array([4], (0, 255))))
        b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
            bins=dict(b=vdc.bin_array([4], (0, 255))))
        axb: vdc.Cross = vdc.cross(lambda s: s.a, lambda s: s.b, **cross_kwargs)

    return my_cg


def _hit_all(cg):
    for k in range(4):
        for j in range(4):
            cg.sample(k * 64, j * 64)


class TestCoverageCrossBinsof(DcTestCase):

    def test_intersect_and_ignores_one_bin(self):
        # ignore (a in bin0 [0..63]) AND (b in bin3 [192..255]) -> exactly 1 bin.
        cg = _grid_cg(ignore_bins=dict(
            corner=lambda s: vdc.binsof(s.a).intersect([(0, 63)])
            & vdc.binsof(s.b).intersect([(192, 255)])))()
        self.assertEqual(cg.axb._model.n_ignore, 1)
        # Hitting only the ignored combo never advances coverage.
        cg.sample(0, 192)
        self.assertEqual(cg.axb.get_coverage(), 0)
        # Hitting every combo covers all 15 valid bins -> 100%.
        _hit_all(cg)
        self.assertEqual(cg.axb.get_coverage(), 100)

    def test_intersect_partial_coverage_denominator(self):
        # Denominator excludes the ignored bin: 1 of 15 valid -> 1/15.
        cg = _grid_cg(ignore_bins=dict(
            corner=lambda s: vdc.binsof(s.a).intersect([(0, 63)])
            & vdc.binsof(s.b).intersect([(192, 255)])))()
        cg.sample(0, 0)                       # (a0,b0) — a valid bin
        self.assertAlmostEqual(cg.axb.get_coverage(), 100.0 / 15)

    def test_or_combines_selections(self):
        # ignore (a in bin0) OR (b in bin3): a0 row (4) + b3 col (4) - overlap (1)
        # = 7 ignored, 9 valid.
        cg = _grid_cg(ignore_bins=dict(
            x=lambda s: vdc.binsof(s.a).intersect([(0, 63)])
            | vdc.binsof(s.b).intersect([(192, 255)])))()
        self.assertEqual(cg.axb._model.n_ignore, 7)
        _hit_all(cg)
        self.assertEqual(cg.axb.get_coverage(), 100)

    def test_invert_selection(self):
        # ignore NOT(a in bin0) -> ignore a bins 1,2,3 (12 bins); valid = a0 row (4).
        cg = _grid_cg(ignore_bins=dict(
            x=lambda s: ~vdc.binsof(s.a).intersect([(0, 63)])))()
        self.assertEqual(cg.axb._model.n_ignore, 12)

    def test_whole_coverpoint_term(self):
        # binsof(a) (no intersect) selects all of a; combined with b's bin3 -> the
        # whole b3 column ignored (4 bins) regardless of a. valid = 12.
        cg = _grid_cg(ignore_bins=dict(
            col=lambda s: vdc.binsof(s.a)
            & vdc.binsof(s.b).intersect([(192, 255)])))()
        self.assertEqual(cg.axb._model.n_ignore, 4)

    def test_whole_coverpoint_ignore_all(self):
        # binsof(a) alone selects every cross bin -> all ignored; an empty cross is
        # 100% covered (design §2.8: warn, don't crash).
        cg = _grid_cg(ignore_bins=dict(all=lambda s: vdc.binsof(s.a)))()
        self.assertEqual(cg.axb._model.n_ignore, 16)
        self.assertEqual(cg.axb.get_coverage(), 100)

    def test_binsof_non_component_raises(self):
        # binsof referencing a coverpoint not in the cross -> clear error at build
        # (build happens in the covergroup constructor).
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 255))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 255))))
            c: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(c=vdc.bin_array([4], (0, 255))))
            axb: vdc.Cross = vdc.cross(
                lambda s: s.a, lambda s: s.b,
                ignore_bins=dict(bad=lambda s: vdc.binsof(s.c)))

        with self.assertRaises(ValueError) as ctx:
            my_cg()
        self.assertIn("not in cross", str(ctx.exception))

    def test_binsof_requires_coverpoint(self):
        # binsof() on a non-coverpoint is a clear TypeError.
        with self.assertRaises(TypeError):
            vdc.binsof(42)

    def test_illegal_bin_excluded_and_tracked(self):
        # An illegal cross bin is excluded from coverage (like ignore) and its hits
        # are tracked separately (parity with coverpoint illegal bins, SV §19.6).
        cg = _grid_cg(illegal_bins=dict(
            bad=lambda s: vdc.binsof(s.a).intersect([(0, 63)])
            & vdc.binsof(s.b).intersect([(192, 255)])))()
        m = cg.axb._model
        self.assertEqual(m.n_illegal, 1)
        self.assertEqual(m.n_ignore, 0)
        # The illegal cross bin is (a0,b3) -> idx 0*4+3 = 3.
        self.assertTrue(m.get_bin_illegal(3))
        self.assertFalse(m.get_bin_valid(3))
        # Hitting it is tracked but never advances coverage.
        cg.sample(0, 192)
        self.assertEqual(m.get_illegal_bin_hits(3), 1)
        self.assertEqual(cg.axb.get_coverage(), 0)
        # The other 15 bins are the coverage denominator.
        _hit_all(cg)
        self.assertEqual(cg.axb.get_coverage(), 100)
        self.assertEqual(m.get_illegal_bin_hits(3), 2)   # hit again in _hit_all

    def test_ignore_and_illegal_combined(self):
        # Both channels exclude from coverage; denominators stack without double
        # counting. ignore a0-row-with-b0 (1 bin), illegal a3-row-with-b3 (1 bin).
        cg = _grid_cg(
            ignore_bins=dict(
                ig=lambda s: vdc.binsof(s.a).intersect([(0, 63)])
                & vdc.binsof(s.b).intersect([(0, 63)])),
            illegal_bins=dict(
                il=lambda s: vdc.binsof(s.a).intersect([(192, 255)])
                & vdc.binsof(s.b).intersect([(192, 255)])))()
        m = cg.axb._model
        self.assertEqual(m.n_ignore, 1)
        self.assertEqual(m.n_illegal, 1)
        _hit_all(cg)
        self.assertEqual(cg.axb.get_coverage(), 100)   # 14/14 valid bins
