"""dv-solve UNSAT-verdict parity with Boolector (plan Workstream A4).

dv-solve is the *authoritative* UNSAT engine on its own path (Phase A: a primary
non-OK escalates to the complete BV-SAT engine, which decides UNSAT soundly rather
than deferring). The differential XCHECK gate validates *membership* of SAT models
but says nothing when a problem is UNSAT — there is no model to check. This suite
closes that blind spot: for a battery of genuinely-infeasible constraint shapes,
dv-solve and Boolector must AGREE on the UNSAT verdict (both raise SolveFailure),
and for the satisfiable control cases both must succeed.

A divergence here — dv-solve silently producing a "solution" to an infeasible
problem, or failing a feasible one — is a soundness bug the SAT-model XCHECK cannot
catch. Skipped when the dv-solve native library is unavailable.

See doc/notes/dv_solve_test_suite_enhancement_plan.md (Workstream A4).
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solve_failure import SolveFailure
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


# --- infeasible (UNSAT) constraint shapes -------------------------------- #

@vsc.randobj
class RangeConflict(object):
    def __init__(s):
        s.x = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.x > 200
        s.x < 100


@vsc.randobj
class PairCycle(object):
    def __init__(s):
        s.a = vsc.rand_uint8_t()
        s.b = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.a < s.b
        s.b < s.a


@vsc.randobj
class InsideGapConflict(object):
    def __init__(s):
        s.x = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.x.inside(vsc.rangelist(1, 2, 3))
        s.x == 50


@vsc.randobj
class EqContradiction(object):
    def __init__(s):
        s.x = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.x == 10
        s.x == 20


@vsc.randobj
class UniqueImpossible(object):
    """Two vars both pinned to 0 but required unique — no assignment exists."""
    def __init__(s):
        s.a = vsc.rand_uint8_t()
        s.b = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.a == 0
        s.b == 0
        vsc.unique(s.a, s.b)


@vsc.randobj
class ConstConstraintFalse(object):
    """A hard constraint over only a *non-rand* field (``k``==11) that the field's
    fixed value violates. The constraint has no solver variable, so a back-end
    that drops variable-free constraints would silently ignore it and "solve" an
    infeasible problem. Boolector evaluates it and reports UNSAT; dv-solve must
    agree (regression: variable-free constant-false constraint was dropped)."""
    def __init__(s):
        s.k = vsc.uint8_t(11)          # non-rand state field
        s.r = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.k < 10                       # all-constant -> false
        s.r < 200


# --- satisfiable controls ------------------------------------------------ #

@vsc.randobj
class FeasibleTight(object):
    def __init__(s):
        s.x = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.x > 99
        s.x < 101            # only x == 100


@vsc.randobj
class ConstConstraintTrue(object):
    """Control for ConstConstraintFalse: the same variable-free constraint, but
    satisfied by the non-rand field's value — must stay SAT on both back-ends."""
    def __init__(s):
        s.k = vsc.uint8_t(5)           # non-rand state field, satisfies k < 10
        s.r = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.k < 10                       # all-constant -> true
        s.r < 200


UNSAT_CLASSES = [RangeConflict, PairCycle, InsideGapConflict,
                 EqContradiction, UniqueImpossible, ConstConstraintFalse]
SAT_CLASSES = [FeasibleTight, ConstConstraintTrue]


def _verdict(cls):
    """Return True if randomize() succeeds, False if it raises SolveFailure."""
    obj = cls()
    try:
        obj.randomize()
        return True
    except SolveFailure:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveUnsatParity(VscTestCase):

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _verdicts(self, cls):
        ctor.set_solver_backend("boolector")
        btor = _verdict(cls)
        ctor.set_solver_backend("dv-solve")
        dvs = _verdict(cls)
        return btor, dvs

    def test_unsat_verdict_parity(self):
        for cls in UNSAT_CLASSES:
            btor, dvs = self._verdicts(cls)
            self.assertFalse(btor, "%s: Boolector should report UNSAT" % cls.__name__)
            self.assertEqual(
                dvs, btor,
                "%s: dv-solve verdict (%s) disagrees with Boolector (UNSAT) — "
                "dv-solve produced a 'solution' to an infeasible problem"
                % (cls.__name__, "SAT" if dvs else "UNSAT"))

    def test_sat_verdict_parity(self):
        for cls in SAT_CLASSES:
            btor, dvs = self._verdicts(cls)
            self.assertTrue(btor, "%s: Boolector should be SAT" % cls.__name__)
            self.assertEqual(
                dvs, btor,
                "%s: dv-solve reported UNSAT for a feasible problem" % cls.__name__)

    def test_feasible_control_value(self):
        """The tight feasible case has a unique solution; dv-solve must find it."""
        ctor.set_solver_backend("dv-solve")
        obj = FeasibleTight()
        obj.randomize()
        self.assertEqual(int(obj.x), 100)


if __name__ == "__main__":
    unittest.main()
