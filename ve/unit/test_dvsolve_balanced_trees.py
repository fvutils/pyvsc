"""Large conjunctions and sampler parity planes are built as balanced trees.

The translator's ``_conj`` chained its terms left-deep, so a body of n terms
nested n deep. Both engines reject expressions nested ~65536 deep (measured:
a left-deep AND of 50000 terms compiles, 65535 does not; the compile error
text still says 20000), so a conjunction that large failed with
``CompileUnsupportedError`` on the primary and ``dvs_bbsolver_new failed`` on
BV-SAT. The BV-SAT sampler's XOR parity planes had the same shape (one term
per hashed bit of every variable). Balanced, the depth is log2(n).

Skipped when the dv-solve native library is unavailable.
"""
import random
import unittest

from vsc.model.solver.backend import select_backend


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


N_TERMS = 70000   # past the ~65536 nesting limit


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestBalancedTrees(unittest.TestCase):

    def _builder(self, n_vars):
        from dv_solve.builder import SolveProblemBuilder
        b = SolveProblemBuilder()
        for v in range(n_vars):
            b.add_var(v, width=8, is_signed=False, lo=0, hi=255)
        return b

    def test_conj_compiles_on_both_engines(self):
        from dv_solve.ctx import SolveCtx
        from dv_solve.bvsat import BVSatCtx, BVSAT_SAT
        from dv_solve.problem import BIN_LT
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator
        n_vars = 64
        b = self._builder(n_vars)
        tr = DvSolveExprTranslator(b, None)
        terms = [b.expr_binary(BIN_LT, b.expr_var(i % n_vars), b.expr_const(200))
                 for i in range(N_TERMS)]
        b.add_constraint(tr._conj(terms))
        buf, _ = b.finalize()
        ctx = SolveCtx(buf)          # raised CompileUnsupportedError (depth)
        self.assertIsNotNone(ctx)
        with BVSatCtx(buf) as bb:    # raised "dvs_bbsolver_new failed"
            self.assertEqual(bb.check(seed=1), BVSAT_SAT)

    def test_conj_small_and_empty(self):
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator
        b = self._builder(1)
        tr = DvSolveExprTranslator(b, None)
        one = b.expr_var(0)
        self.assertEqual(tr._conj([one]), one)
        self.assertIsNotNone(tr._conj([]))

    def test_parity_plane_builds(self):
        from dv_solve.bvsat import BVSatCtx, BVSAT_SAT
        from vsc.model.solver.bvsat_sampler import _append_one_plane
        n_vars = N_TERMS // 8
        b = self._builder(n_vars)
        bits = [(v, k) for v in range(n_vars) for k in range(8)]
        self.assertTrue(_append_one_plane(b, bits, random.Random(1)))
        buf, _ = b.finalize()
        with BVSatCtx(buf) as bb:    # raised "dvs_bbsolver_new failed"
            self.assertEqual(bb.check(seed=1), BVSAT_SAT)


if __name__ == "__main__":
    unittest.main()
