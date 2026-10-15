"""V21 (fallback_elimination_v2_plan.md) — a defer site that no front-end
shape reaches is a dv-solve bug, so it raises ``BackendInternalError``,
which is not a fallback trigger.

Coverage over ve/unit, ve/unit_dc and the residual probes found these sites
never reached: a node with no translation, an op no front end builds, a
non-array subscript, an empty-array select, an unguarded aggregate over a
co-solved random-size array, and a primary miss with no problem buffer.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.solver.backend import (
    BackendIncomplete, BackendInternalError, select_backend)
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveInternalError(VscTestCase):

    def _translator(self):
        from dv_solve.builder import SolveProblemBuilder
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator
        b = SolveProblemBuilder()
        self.addCleanup(b.destroy)
        return DvSolveExprTranslator(b, None)

    def test_not_a_fallback_trigger(self):
        self.assertFalse(issubclass(BackendInternalError, BackendIncomplete))

    def test_binary_not_op(self):
        e = ExprBinModel(ExprLiteralModel(1, False, 8), BinExprType.Not,
                         ExprLiteralModel(2, False, 8))
        with self.assertRaises(BackendInternalError) as cm:
            self._translator().translate(e)
        self.assertIn("please report", str(cm.exception))

    def test_node_without_translation(self):
        e = ExprRangeModel(ExprLiteralModel(1, False, 8),
                           ExprLiteralModel(2, False, 8))
        with self.assertRaises(BackendInternalError):
            self._translator().translate(e)

    def test_propagates_with_fallback_enabled(self):
        """The fallback chain must not serve an internal error: it reaches the
        caller even when the fallback is on."""
        import vsc.model.randomizer as rnd
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator

        def boom(self, *args, **kwargs):
            raise BackendInternalError("injected")

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.a > 3

        saved_nf, saved_fb = rnd._NO_FALLBACK, rnd._FALLBACK
        saved_tr = DvSolveExprTranslator.translate
        rnd._NO_FALLBACK, rnd._FALLBACK = False, True
        DvSolveExprTranslator.translate = boom
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()
        try:
            with self.assertRaises(BackendInternalError):
                C().randomize()
        finally:
            rnd._NO_FALLBACK, rnd._FALLBACK = saved_nf, saved_fb
            DvSolveExprTranslator.translate = saved_tr
            ctor.set_solver_backend(None)

    def test_bvsat_undecided(self):
        """V22: BV-SAT undecided on a RandSet is a bug, not a defer, even with
        the fallback on. An 80-bit field routes the RandSet to BV-SAT."""
        import vsc.model.randomizer as rnd
        from dv_solve.bvsat import BVSatCtx, BVSAT_UNKNOWN

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(80)

            @vsc.constraint
            def c(s):
                s.a > 3

        saved_nf, saved_check = rnd._NO_FALLBACK, BVSatCtx.check
        saved_sample = BVSatCtx.sample
        saved_fb = rnd._FALLBACK
        rnd._NO_FALLBACK, rnd._FALLBACK = False, True
        # Undecided both ways in: the engine's sampler (V19), which gives the
        # verdict on a plain serve, and the check it falls through to.
        BVSatCtx.check = lambda self, *a, **k: BVSAT_UNKNOWN
        BVSatCtx.sample = lambda self, *a, **k: BVSAT_UNKNOWN
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()
        try:
            with self.assertRaises(BackendInternalError) as cm:
                C().randomize()
            self.assertIn("could not decide", str(cm.exception))
        finally:
            rnd._NO_FALLBACK, rnd._FALLBACK = saved_nf, saved_fb
            BVSatCtx.check, BVSatCtx.sample = saved_check, saved_sample
            ctor.set_solver_backend(None)


if __name__ == "__main__":
    unittest.main()
