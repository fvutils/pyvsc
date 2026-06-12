'''
Created on Oct 25, 2020

@author: ballance
'''
from enum import IntEnum, auto
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


class TestSolveFailure(VscTestCase):
    
    def test_fail_enum(self):
        
        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj(srcinfo=True)
        class my_c(object):
            
            def __init__(self):
                self.e = vsc.rand_enum_t(my_e)
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a == 1
                with vsc.if_then(self.a == 2):
                    self.e == my_e.A
                
        it = my_c()

        try:        
            with it.randomize_with(solve_fail_debug=True):
                it.a == 2
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))


    def test_fail_constraint_pair(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                self.d = vsc.rand_uint8_t()
                
            @vsc.constraint
            def abcd_c(self):
                self.c > self.b
                self.a < self.b
                self.c < self.a
                self.c < 10
                self.a > 0
                self.b <= 20
                
        it = my_c()

        try:
            it.randomize()
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))

    @unittest.skipUnless(_dvsolve_available(),
                         "dv-solve native library not available")
    def test_diagnostics_with_dvsolve_primary(self):
        # Phase E / E4-1: with dv-solve as the primary back-end, an UNSAT
        # randomize must still produce human-facing diagnostics. dv-solve decides
        # UNSAT authoritatively (BV-SAT), then create_diagnostics explains it via
        # the lazily-imported Boolector — which must keep working. Locks that the
        # diagnostics path is not broken by the dv-solve integration.
        ctor.set_solver_backend("dv-solve")
        try:
            @vsc.randobj
            class my_c(object):
                def __init__(self):
                    self.a = vsc.rand_uint8_t()
                @vsc.constraint
                def a_c(self):
                    self.a > 200
                    self.a < 100

            it = my_c()
            try:
                it.randomize(solve_fail_debug=1)
                self.fail("Expected a solve failure")
            except vsc.SolveFailure as e:
                diag = e.diagnostics or ""
                self.assertTrue(diag.strip(),
                                "no diagnostics produced under dv-solve primary")
                # The Boolector-backed explainer lists the contributing
                # constraints.
                self.assertIn("a", diag)
        finally:
            ctor.set_solver_backend(None)
    