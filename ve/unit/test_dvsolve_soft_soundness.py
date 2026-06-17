"""dv-solve soft-constraint soundness (integration-level guard for issue I-1).

A *soft* constraint that conflicts with nothing — no hard constraint and no other
kept soft — is trivially satisfiable, so a maximal priority-respecting relaxation
MUST honor it. dropping such a soft is a soundness bug, not a distribution choice.

These tests lock that invariant end-to-end through the pyvsc -> dv-solve path. They
were added after the primary engine's *subtractive* MaxSAT relaxation was found to
shed satisfiable lower-preference softs as collateral when reaching a conflicting
higher-preference sibling (the intermittent ``test_constraint_soft.test_soft_nested``
failure). The C-level deterministic lock lives in
``packages/dv-solve/tests/unit/test_soft.py::test_soft_no_collateral_drop_primary``;
this file is the matching integration-level gate plus a per-seed determinism lock.

Run under the no-fallback guard so a regression that silently defers to Boolector
fails here rather than passing through the oracle. Skipped when the dv-solve native
library is unavailable.

See doc/notes/dv_solve_test_suite_enhancement_plan.md (Workstreams A/B, issue I-1).
"""
import random
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _no_fallback():
    """Make any fall-through to Boolector raise, so a soft that is not served
    natively by dv-solve fails the test instead of being served by the oracle."""
    import vsc.model.solver.boolector_backend as bb
    orig = bb.BoolectorBackend.solve_randset

    def _raise(self, rs, *a, **k):
        raise AssertionError("dv-solve fell back to Boolector for a RandSet")

    bb.BoolectorBackend.solve_randset = _raise
    try:
        yield
    finally:
        bb.BoolectorBackend.solve_randset = orig


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveSoftSoundness(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    # ---------------------------------------------------------------- #
    # Flat scalar shape — exercises the primary relaxation path (no
    # arrays / conjunctive bodies that would force the BV-SAT serve path).
    # hard x==20; soft x==5 conflicts (must relax); softs y==40, z==50 are
    # independent and must always be kept. This is the EQ-only twin of the
    # C-level collateral-drop repro.
    # ---------------------------------------------------------------- #
    def test_independent_softs_honored_flat(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()
                s.z = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.x == 20                 # hard
                vsc.soft(s.x == 5)        # conflicts with hard -> relax
                vsc.soft(s.y == 40)       # independent -> keep
                vsc.soft(s.z == 50)       # independent -> keep

        obj = C()
        with _no_fallback():
            for seed in range(40):
                random.seed(seed)
                obj.randomize()
                self.assertEqual(int(obj.x), 20, "hard x==20 must hold")
                self.assertEqual(int(obj.y), 40,
                                 "independent soft y==40 dropped as collateral")
                self.assertEqual(int(obj.z), 50,
                                 "independent soft z==50 dropped as collateral")

    # NOTE — why there is no "nested bundled-soft" case here. The shape that
    # originally flaked (test_constraint_soft.test_soft_nested, multiple softs in
    # one guarded `if_then` block where some conflict) is NOT a sound per-soft
    # invariant: pyvsc lowers a guarded block's softs as a bundle, so when one
    # conflicts the whole bundle is relaxed and the *independent* softs drop too —
    # confirmed identical on Boolector, and seed-dependent (test_soft_nested only
    # passes because it uses a single fixed seed). That is backend-agnostic
    # front-end behavior, not a dv-solve soundness property, so asserting it here
    # would be wrong. The dv-solve-specific collateral bug (issue I-1) lives in the
    # *primary relaxation* and is exercised by the flat case above plus the
    # deterministic C lock test_soft.py::test_soft_no_collateral_drop_primary.

    # ---------------------------------------------------------------- #
    # Priority: mutually-exclusive softs at distinct priorities. Only the
    # highest-preference one can survive, and it must.
    # ---------------------------------------------------------------- #
    def test_highest_priority_soft_kept(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                # default priority is declaration-ordered; later-declared wins in
                # pyvsc (SV soft override). Make x==30 the kept one.
                vsc.soft(s.x == 10)
                vsc.soft(s.x == 20)
                vsc.soft(s.x == 30)

        obj = C()
        with _no_fallback():
            for seed in range(20):
                random.seed(seed)
                obj.randomize()
                self.assertEqual(int(obj.x), 30,
                                 "highest-preference soft (x==30) must be kept")

    # ---------------------------------------------------------------- #
    # Determinism lock: same seed -> identical value stream. Guards against a
    # non-deterministic relaxation/sampler change silently shifting results.
    # ---------------------------------------------------------------- #
    def test_soft_relaxation_deterministic(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.x == 20
                vsc.soft(s.x == 5)        # conflict
                vsc.soft(s.y.inside(vsc.rangelist(vsc.rng(0, 255))))

        def run():
            obj = C()
            vals = []
            with _no_fallback():
                for _ in range(50):
                    obj.randomize()
                    vals.append((int(obj.x), int(obj.y)))
            return vals

        random.seed(12345)
        first = run()
        random.seed(12345)
        second = run()
        self.assertEqual(first, second,
                         "soft-bearing solve not reproducible for a fixed seed")


if __name__ == "__main__":
    unittest.main()
