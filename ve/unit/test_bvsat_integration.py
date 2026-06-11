'''
Phase-A integration tests (T-I): the dv-solve back-end uses its internal BV-SAT
completeness engine for an *authoritative UNSAT verdict* without invoking the
external Boolector fallback solver.

See doc/notes/dv_solve_phaseA_bvsat_plan.md.

Skipped automatically when the dv-solve native library is unavailable.

@author: solver-backend integration
'''
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solve_failure import SolveFailure
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestBVSatIntegration(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _boolector_solver_spy(self):
        """Patch the Boolector back-end's solve_randset to count invocations,
        returning (restore_fn, counter)."""
        btor = select_backend("boolector")
        cls = type(btor)
        orig = cls.solve_randset
        counter = {"n": 0}

        def spy(self, *a, **k):
            counter["n"] += 1
            return orig(self, *a, **k)

        cls.solve_randset = spy
        return (lambda: setattr(cls, "solve_randset", orig)), counter

    def test_joint_unsat_authoritative_no_boolector(self):
        """A jointly-unsatisfiable system (individual field domains fine) must
        raise SolveFailure, decided by dv-solve's BV-SAT engine — the Boolector
        fallback solver must NOT be invoked for the verdict."""
        @vsc.randobj
        class Bad(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(16)

            @vsc.constraint
            def c(self):
                self.a + self.b == 5
                self.a == 3
                self.b == 4   # 3 + 4 = 7 != 5 -> UNSAT (bounds individually ok)

        restore, counter = self._boolector_solver_spy()
        try:
            it = Bad()
            with self.assertRaises(SolveFailure):
                it.randomize()
            self.assertEqual(
                counter["n"], 0,
                "Boolector solver was invoked for the UNSAT verdict; dv-solve "
                "should be authoritative")
        finally:
            restore()

    def test_sat_still_solves(self):
        """A satisfiable system still solves correctly under dv-solve (sanity:
        the BV-SAT integration doesn't disturb the normal SAT path)."""
        @vsc.randobj
        class Ok(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(16)
                self.c = vsc.rand_bit_t(32)

            @vsc.constraint
            def cc(self):
                self.c == self.a + self.b
                self.a > 0
                self.b > 0

        it = Ok()
        for _ in range(20):
            it.randomize()
            self.assertEqual(int(it.c), int(it.a) + int(it.b))
            self.assertGreater(int(it.a), 0)
            self.assertGreater(int(it.b), 0)


if __name__ == "__main__":
    unittest.main()
