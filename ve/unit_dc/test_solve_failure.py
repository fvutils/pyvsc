'''
Dataclass-front-end parallel of ve/unit/test_solve_failure.py.

Scalar UNSAT detection + diagnostics, plus the enum UNSAT case (Phase 2 enums).
'''
import unittest
from enum import IntEnum, auto

import vsc.dc as vdc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from dc_test_case import DcTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


class TestSolveFailure(DcTestCase):

    def test_fail_enum(self):

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            e: my_e = vdc.rand()
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def a_c(self):
                self.a == 1
                with vdc.if_then(self.a == 2):
                    self.e == my_e.A

        it = my_c()

        # a==1 from the type constraint, inline forces a==2 -> contradiction.
        # NOTE (dc idiom): inline constraints go through the `as` proxy — dataclass
        # fields are plain values, so `it.a == 2` on the object itself would be a
        # no-op Python comparison. (Classic pyvsc allows the no-`as` form because
        # the object's attributes are expr-mode-aware.)
        try:
            with it.randomize_with(solve_fail_debug=True) as itc:
                itc.a == 2
            self.fail("Expected a solve failure")
        except vdc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))

    def test_fail_constraint_pair(self):

        @vdc.dataclass
        class my_c(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
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
        except vdc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))

    @unittest.skipUnless(_dvsolve_available(),
                         "dv-solve native library not available")
    def test_diagnostics_with_dvsolve_primary(self):
        ctor.set_solver_backend("dv-solve")
        try:
            @vdc.dataclass
            class my_c(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def a_c(self):
                    self.a > 200
                    self.a < 100

            it = my_c()
            try:
                it.randomize(solve_fail_debug=1)
                self.fail("Expected a solve failure")
            except vdc.SolveFailure as e:
                diag = e.diagnostics or ""
                self.assertTrue(diag.strip(),
                                "no diagnostics produced under dv-solve primary")
                self.assertIn("a", diag)
        finally:
            ctor.set_solver_backend(None)
