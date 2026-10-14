"""_make_solve_ctx: a large problem gets a solver context.

The helper sized a working-pool buffer at ~40x the serialized problem and
retried up to 16 MiB. A problem over ~420 KB (e.g. `unique` over 170
elements, ~14k pairwise terms) put the first estimate above the cap, so the
loop made no attempt at all and raised "solver pool sizing failed". The
RandSet then left the fast engine for the BV-SAT sampler, which is far
slower on such a problem. dv-solve's context now grows its own pool (and
ignores ctx_buf_size), so the helper tries that first; the sized retries
remain only for an older fixed-pool dv-solve.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
import warnings

from vsc.model.solver.backend import select_backend
import vsc.model.solver.dvsolve_backend as dvb


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


def _small_problem():
    from dv_solve.builder import SolveProblemBuilder
    from dv_solve.problem import BIN_LT
    b = SolveProblemBuilder()
    b.add_var(0, width=8, is_signed=False, lo=0, hi=255)
    b.add_var(1, width=8, is_signed=False, lo=0, hi=255)
    b.add_constraint(b.expr_binary(BIN_LT, b.expr_var(0), b.expr_var(1)))
    return b.finalize()


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestCtxSizing(unittest.TestCase):

    def test_estimate_above_cap_still_builds(self):
        buf, _ = _small_problem()
        # A problem size whose 40x estimate exceeds _CTX_BUF_MAX.
        big = dvb._CTX_BUF_MAX // dvb._CTX_BUF_PER_PROBLEM_BYTE + 1
        ctx = dvb._make_solve_ctx(buf, big)
        self.assertIsNotNone(ctx)

    def test_no_deprecated_size_argument(self):
        buf, sz = _small_problem()
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            dvb._make_solve_ctx(buf, sz)


if __name__ == "__main__":
    unittest.main()
