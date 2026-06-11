"""Standing regression for the BV-SAT XOR/parity uniform sampler
(``vsc.model.solver.bvsat_sampler``).

Exercises the sampler directly (no pyvsc backend, no env flags) against a wide
variable with a small feasible set — the case that motivated it (a clustered
kissat model leaves values unreachable). Asserts full coverage, in-range values,
and per-seed determinism.

Skips automatically when the dv-solve native library is unavailable.
"""
import unittest

try:
    from dv_solve.lib import _load_lib
    from dv_solve.builder import SolveProblemBuilder
    from dv_solve.problem import BIN_LTE, BIN_GTE, BIN_AND
    from vsc.model.solver import bvsat_sampler
    _HAVE_DVSOLVE = _load_lib() is not None
except Exception:
    _HAVE_DVSOLVE = False


class _Field(object):
    """Minimal stand-in for a pyvsc field: just captures set_val()."""
    __slots__ = ("val",)

    def __init__(self):
        self.val = None

    def set_val(self, v):
        self.val = v


def _make_base_factory(width, lo, hi):
    """Factory rebuilding a one-variable base problem: a width-bit unsigned var
    constrained to [lo, hi]. The explicit bound constraint references the var so
    the BV-SAT engine asserts its declared bounds (pins the high bits the sampler
    does not hash)."""
    def mk():
        b = SolveProblemBuilder()
        b.add_var(0, width, False, lo, hi)
        b.add_constraint(b.expr_binary(BIN_GTE, b.expr_var(0), b.expr_const(lo)))
        b.add_constraint(b.expr_binary(BIN_LTE, b.expr_var(0), b.expr_const(hi)))
        return b
    return mk


@unittest.skipUnless(_HAVE_DVSOLVE, "dv-solve native library unavailable")
class TestBvsatSampler(unittest.TestCase):

    def test_coverage_wide_small_range(self):
        # uint64 var, feasible {0..19}: kissat clusters and misses values; the
        # sampler must hit every value over a reasonable number of draws.
        mk = _make_base_factory(64, 0, 19)
        sample_vars = [(0, 64, 0, 19, False)]
        hist = [0] * 20
        for i in range(400):
            f = _Field()
            ok = bvsat_sampler.sample(mk, [(f, 0)], sample_vars, seed=i)
            self.assertTrue(ok, "sampler failed to serve a known-SAT problem")
            self.assertTrue(0 <= f.val <= 19,
                            "sampler produced out-of-range value %r" % f.val)
            hist[f.val] += 1
        self.assertTrue(all(h > 0 for h in hist),
                        "values unreachable: %s" % hist)

    def test_determinism(self):
        # Same seed stream -> identical value stream (per-seed determinism).
        mk = _make_base_factory(64, 0, 19)
        sample_vars = [(0, 64, 0, 19, False)]

        def run():
            out = []
            for i in range(60):
                f = _Field()
                bvsat_sampler.sample(mk, [(f, 0)], sample_vars, seed=i)
                out.append(f.val)
            return out

        self.assertEqual(run(), run())

    def test_multi_var(self):
        # Two independent wide vars, small ranges: both must be covered and in
        # range. Exercises bit selection / m estimate across >1 var.
        def mk():
            b = SolveProblemBuilder()
            b.add_var(0, 64, False, 0, 7)
            b.add_var(1, 32, False, 0, 4)
            for vid, hi in ((0, 7), (1, 4)):
                b.add_constraint(b.expr_binary(BIN_LTE, b.expr_var(vid),
                                               b.expr_const(hi)))
            return b
        sample_vars = [(0, 64, 0, 7, False), (1, 32, 0, 4, False)]
        seen0, seen1 = set(), set()
        for i in range(400):
            f0, f1 = _Field(), _Field()
            ok = bvsat_sampler.sample(mk, [(f0, 0), (f1, 1)], sample_vars, seed=i)
            self.assertTrue(ok)
            self.assertTrue(0 <= f0.val <= 7 and 0 <= f1.val <= 4,
                            "out of range: %r, %r" % (f0.val, f1.val))
            seen0.add(f0.val)
            seen1.add(f1.val)
        self.assertEqual(seen0, set(range(8)))
        self.assertEqual(seen1, set(range(5)))


if __name__ == "__main__":
    unittest.main()
