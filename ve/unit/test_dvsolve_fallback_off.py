"""The Boolector fallback is off by default (v2 plan V23).

A RandSet dv-solve cannot serve raises ``vsc.SolverUnsupported``, naming the
reason, instead of being solved by Boolector. ``VSC_DVSOLVE_FALLBACK=boolector``
(``randomizer._FALLBACK``) is the safety valve for 2.0; strict mode
(``VSC_DVSOLVE_NO_FALLBACK``) beats it.

The gap used is a field wider than dv-solve's width ceiling. The ceiling is
2^24 bits since V26; the tests lower it to 300 bits, so the valve's Boolector
solve stays small, except test_engine_ceiling, which uses the real one.
Skipped when the dv-solve native library is unavailable.
"""
import os
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import (
    select_backend, BackendIncomplete, SolverUnsupported)
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase, requires_boolector


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


def _wide():
    @vsc.randobj
    class Wide(object):
        def __init__(s):
            s.w = vsc.rand_bit_t(dvb._MAX_FIELD_WIDTH + 1)

        @vsc.constraint
        def c(s):
            s.w > 5
    return Wide()


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveFallbackOff(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self.disable_t0()   # T0 would serve `w > 5` without a solver
        self._saved = (rnd._FALLBACK, rnd._NO_FALLBACK, dvb._MAX_FIELD_WIDTH)
        rnd._FALLBACK, rnd._NO_FALLBACK = False, False
        dvb._MAX_FIELD_WIDTH = 300

    def tearDown(self):
        rnd._FALLBACK, rnd._NO_FALLBACK, dvb._MAX_FIELD_WIDTH = self._saved
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_default_raises_solver_unsupported(self):
        with self.assertRaises(SolverUnsupported) as cm:
            _wide().randomize()
        e = cm.exception
        self.assertEqual(e.reason_code, "width")
        self.assertIn("reason: width", str(e))
        self.assertIn("width 301 exceeds 300 bits", str(e))
        self.assertIn("VSC_DVSOLVE_FALLBACK=boolector", str(e))
        # Code that caught the old error still catches it.
        self.assertIsInstance(e, BackendIncomplete)
        self.assertIs(vsc.SolverUnsupported, SolverUnsupported)

    def test_engine_ceiling(self):
        """The real ceiling is the engine's DVS_MAX_WIDTH (2^24 bits), read
        from the library, and one bit past it raises before anything is
        built."""
        dvb._MAX_FIELD_WIDTH = self._saved[2]
        self.assertEqual(dvb._MAX_FIELD_WIDTH, dvb._engine_max_width())
        self.assertEqual(dvb._MAX_FIELD_WIDTH, 1 << 24)
        with self.assertRaises(SolverUnsupported) as cm:
            _wide().randomize()
        self.assertIn("width %d exceeds %d bits" % ((1 << 24) + 1, 1 << 24),
                      str(cm.exception))

    def test_default_never_builds_boolector(self):
        calls = []
        orig = rnd.select_backend

        def spy(name):
            calls.append(name)
            return orig(name)
        rnd.select_backend = spy
        try:
            with self.assertRaises(SolverUnsupported):
                _wide().randomize()
        finally:
            rnd.select_backend = orig
        self.assertNotIn("boolector", calls)

    @requires_boolector
    def test_valve_serves_with_boolector(self):
        rnd._FALLBACK = True
        obj = _wide()
        for _ in range(3):
            obj.randomize()
            self.assertGreater(int(obj.w), 5)

    def test_strict_beats_valve(self):
        rnd._FALLBACK, rnd._NO_FALLBACK = True, True
        with self.assertRaises(SolverUnsupported) as cm:
            _wide().randomize()
        self.assertIn("VSC_DVSOLVE_NO_FALLBACK", str(cm.exception))

    def test_setting_parse(self):
        saved = os.environ.pop("VSC_DVSOLVE_FALLBACK", None)
        try:
            self.assertFalse(rnd._fallback_setting(), "unset")
            for raw, expected in (("boolector", True), ("Boolector", True),
                                  ("", False), ("0", False), ("off", False),
                                  ("none", False)):
                os.environ["VSC_DVSOLVE_FALLBACK"] = raw
                self.assertEqual(rnd._fallback_setting(), expected, raw)
            os.environ["VSC_DVSOLVE_FALLBACK"] = "1"
            with self.assertRaises(Exception):
                rnd._fallback_setting()
        finally:
            os.environ.pop("VSC_DVSOLVE_FALLBACK", None)
            if saved is not None:
                os.environ["VSC_DVSOLVE_FALLBACK"] = saved


if __name__ == "__main__":
    unittest.main()
