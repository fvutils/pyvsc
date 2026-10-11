"""
Base TestCase for the parallel dataclass-front-end suite (``ve/unit_dc``).

Mirrors ``ve/unit/vsc_test_case.py`` exactly (same seeded determinism and
ctor setup/teardown) so results are directly comparable to the classic suite.
"""
from unittest import TestCase
import random
import unittest

from vsc.impl import ctor
from vsc.model.solver.boolector_backend import BoolectorBackend
from vsc.model.solver.dvsolve_backend import DvSolveBackend

# Mirrors ve/unit/vsc_test_case.requires_boolector: for a test whose subject is
# Boolector itself (an XCHECK oracle, a Boolector reference solve).
requires_boolector = unittest.skipUnless(
    BoolectorBackend.available(), "needs pyboolector")


# For a test that pins dv-solve (its plan cache, T0 equivalence against it). The
# boolector CI leg does not install dv-solve. Check availability here, not with
# a try around ctor.set_solver_backend(): that only records the name and never
# raises, so the failure would surface later, at randomize().
def dvsolve_available():
    return DvSolveBackend.available()


requires_dvsolve = unittest.skipUnless(dvsolve_available(), "needs dv-solve")


def known_gap_without_boolector(fn):
    """A test dv-solve passes today only because it hands the RandSet to
    Boolector. Without pyboolector it is an EXPECTED failure rather than a skip:
    the gap stays visible, and closing it turns the run red (unexpected success)
    so the marker gets removed."""
    if BoolectorBackend.available():
        return fn
    return unittest.expectedFailure(fn)


class DcTestCase(TestCase):

    def setUp(self):
        random.seed(0)
        ctor.test_setup()

    def tearDown(self):
        ctor.test_teardown()

    def disable_t0(self):
        """Keep this test on the solver. Mirrors VscTestCase.disable_t0 -- see
        there for why a back-end test needs it."""
        import vsc.model.randomizer as _rnd
        saved = _rnd._T0_ENABLED
        _rnd._T0_ENABLED = False

        def _restore():
            _rnd._T0_ENABLED = saved
        self.addCleanup(_restore)
