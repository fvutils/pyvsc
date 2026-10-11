'''
Phase-0 tests for the pluggable solver back-end (design/plan §0).

Covers:
  P0-T2 -- select_backend / set_solver_backend + VSC_SOLVER precedence
  P0-T3 -- BoolectorBackend.available() False when pyboolector is absent;
           select_backend("boolector") then raises a clear error.

@author: solver-backend integration
'''
import os
import sys
import importlib

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend, SolverBackendIF
from vsc.model.solver.boolector_backend import BoolectorBackend
from vsc_test_case import VscTestCase, requires_boolector


class TestSolverBackend(VscTestCase):

    def tearDown(self):
        # Always clear any programmatic override so tests don't leak state.
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_default_follows_installed_solver(self):
        # With no override and no VSC_SOLVER, the default is boolector when
        # pyboolector is installed and dv-solve otherwise (the no-Boolector CI
        # job covers the second case). When the suite is run with VSC_SOLVER set
        # (e.g. the dv-solve CI job), the default reflects that instead, so only
        # assert the no-env case.
        if "VSC_SOLVER" not in os.environ or os.environ["VSC_SOLVER"] == "":
            expect = ("boolector" if BoolectorBackend.available()
                      else "dv-solve")
            self.assertEqual(ctor.glbl_solver, expect)
        ctor.set_solver_backend(None)
        self.assertEqual(vsc.get_solver_backend(), ctor.glbl_solver)

    def test_default_without_pyboolector_is_dvsolve(self):
        # The default is resolved at import, so call the resolver directly with
        # pyboolector hidden. find_spec reports a None sys.modules entry as
        # absent, the same simulation test_available_false_without_pyboolector
        # uses.
        saved = sys.modules.get("pyboolector", False)
        sys.modules["pyboolector"] = None
        try:
            self.assertEqual(ctor._default_solver(), "dv-solve")
        finally:
            if saved is False:
                del sys.modules["pyboolector"]
            else:
                sys.modules["pyboolector"] = saved

    @requires_boolector
    def test_select_boolector(self):
        b = select_backend("boolector")
        self.assertIsInstance(b, SolverBackendIF)
        self.assertEqual(b.name, "boolector")
        self.assertTrue(b.supports_soft)
        self.assertFalse(b.randomizes_internally)

    @requires_boolector
    def test_select_aliases(self):
        # "btor" is an accepted alias for boolector.
        self.assertEqual(select_backend("btor").name, "boolector")

    def test_unknown_backend_raises(self):
        with self.assertRaises(Exception):
            select_backend("nonesuch")

    def test_override_precedence(self):
        # Programmatic override wins over the env/default value.
        default = ctor.glbl_solver
        self.assertEqual(vsc.get_solver_backend(), default)
        vsc.set_solver_backend("auto")
        self.assertEqual(vsc.get_solver_backend(), "auto")
        # Clearing the override falls back to the default.
        vsc.set_solver_backend(None)
        self.assertEqual(vsc.get_solver_backend(), default)

    def test_auto_resolves(self):
        # auto must resolve to an available back-end (boolector is present).
        b = select_backend("auto")
        self.assertIsInstance(b, SolverBackendIF)

    @requires_boolector
    def test_available_false_without_pyboolector(self):
        # P0-T3: simulate pyboolector being unavailable. Setting the module to
        # None in sys.modules makes `import pyboolector` raise ImportError.
        saved = sys.modules.get("pyboolector", False)
        sys.modules["pyboolector"] = None
        try:
            self.assertFalse(BoolectorBackend.available())
            with self.assertRaises(Exception):
                select_backend("boolector")
        finally:
            if saved is False:
                del sys.modules["pyboolector"]
            else:
                sys.modules["pyboolector"] = saved
        # Sanity: it is available again once restored.
        self.assertTrue(BoolectorBackend.available())
