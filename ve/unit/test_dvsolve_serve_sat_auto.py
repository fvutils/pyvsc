"""Phase F / T-F1a — serve-SAT default is `auto`, decoupled from the fallback.

F-1a makes `VSC_DVSOLVE_BVSAT_SERVE_SAT` a tri-state with `auto` as the default:

  * ``"1"``    — always serve satisfiable problems from BV-SAT (uniform sampler);
  * ``"0"``    — never; defer SAT to the external fallback (the Phase-A posture);
  * ``"auto"`` — serve SAT from BV-SAT *only when no external fallback is
                 available* to serve it. The Randomizer sets the per-instance
                 ``_external_fallback_available`` from its fallback chain.

The point of `auto` is to decouple the serve-SAT *cost* from the *default*: while
Boolector is still the default fallback, `auto` behaves exactly like `"0"` (defer
cheaply); once the fallback is dropped (F-3) dv-solve serves SAT itself with no
second flip. These tests lock both the decision logic and the end-to-end posture.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.rand_state import RandState
from vsc.model.solver.backend import select_backend
from vsc.model.solver.dvsolve_backend import DvSolveBackend
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@vsc.randobj
class _RandSzGappedSize(object):
    # randsz array whose size domain is a gapped set excluding 0 ({1,2,4,8}).
    # The primary bounds search can't decide this; BV-SAT *proves it SAT*, so it
    # is exactly the `bvsat-sat-deferred` (serve / defer) decision point.
    def __init__(s):
        s.l = vsc.randsz_list_t(vsc.uint16_t())

    @vsc.constraint
    def sc(s):
        s.l.size.inside(vsc.rangelist(1, 2, 4, 8))


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveServeSatAuto(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self._saved_mode = dvb._BVSAT_SERVE_SAT_MODE

    def tearDown(self):
        dvb._BVSAT_SERVE_SAT_MODE = self._saved_mode
        ctor.set_solver_backend(None)
        super().tearDown()

    # ------------------------------------------------------------------ #
    # The decision function, exhaustively                                  #
    # ------------------------------------------------------------------ #
    def test_serve_sat_enabled_matrix(self):
        be = DvSolveBackend()
        cases = {
            # (mode, external_fallback_available) -> expected serve-SAT
            ("on", True): True,
            ("on", False): True,
            ("off", True): False,
            ("off", False): False,
            ("auto", True): False,   # fallback present → defer (== "0" today)
            ("auto", False): True,   # nothing else will serve → serve (post F-3)
        }
        for (mode, has_fb), expected in cases.items():
            dvb._BVSAT_SERVE_SAT_MODE = mode
            be._external_fallback_available = has_fb
            self.assertEqual(
                be._serve_sat_enabled(), expected,
                "mode=%r external_fallback_available=%r" % (mode, has_fb))

    def test_default_mode_is_auto(self):
        # With no env override the mode resolves to `auto` (F-1a default).
        import os
        saved = os.environ.pop("VSC_DVSOLVE_BVSAT_SERVE_SAT", None)
        try:
            self.assertEqual(dvb._serve_sat_mode(), "auto")
        finally:
            if saved is not None:
                os.environ["VSC_DVSOLVE_BVSAT_SERVE_SAT"] = saved

    # ------------------------------------------------------------------ #
    # The Randomizer wires the per-instance fallback availability          #
    # ------------------------------------------------------------------ #
    def test_randomizer_sets_fallback_availability(self):
        be = DvSolveBackend()
        r = rnd.Randomizer(RandState(0), backend=be)
        self.assertEqual(
            be._external_fallback_available, bool(r.fallback_backends),
            "Randomizer must set _external_fallback_available from its chain")

    # ------------------------------------------------------------------ #
    # End-to-end: the SAT-deferring shape, per mode                        #
    # ------------------------------------------------------------------ #
    def _deferred_codes(self, n=8):
        """Run the gapped-randsz shape `n` times and return the set of
        `bvsat-sat-deferred` tally keys it produced."""
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            obj = _RandSzGappedSize()
            for _ in range(n):
                obj.randomize()
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        return {k for k in hist if k.split(":")[0] == "bvsat-sat-deferred"}

    def test_auto_defers_while_fallback_present(self):
        # Normal config: Boolector is the fallback, so `auto` == `"0"` — the SAT
        # shape defers (served by the net), behavior unchanged from pre-F-1.
        dvb._BVSAT_SERVE_SAT_MODE = "auto"
        self.assertNotEqual(self._deferred_codes(), set(),
                            "auto with a fallback present should defer SAT")

    def test_explicit_off_defers(self):
        dvb._BVSAT_SERVE_SAT_MODE = "off"
        self.assertNotEqual(self._deferred_codes(), set(),
                            "off should always defer SAT to the fallback")

    def test_explicit_on_serves_natively(self):
        # Opt-in serve: dv-solve serves the SAT shape itself, deferring nothing.
        dvb._BVSAT_SERVE_SAT_MODE = "on"
        self.assertEqual(self._deferred_codes(), set(),
                         "on should serve SAT natively (no bvsat-sat-deferred)")


if __name__ == "__main__":
    unittest.main()
