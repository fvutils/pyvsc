"""Phase G — primary-engine completeness: native unsigned-64 and native
multi-range membership on the dv-solve back-end.

Before Phase G these two shapes returned non-OK from the primary bounds engine,
were proved SAT by BV-SAT, and then served by the Boolector fallback
(``bvsat-sat-deferred``):

  * **G-1 unsigned-64** — the primary used a signed int64 carrier, so any u64
    field whose feasible domain reached the upper half ``[2**63, 2**64-1]``
    deferred (the "2**63 cliff": ``x < 2**63-1`` solved, ``x < 2**63`` did not).
  * **G-2 multi-range ``inside``** — a disjoint membership ``{1,2} U [100,200]``
    lowered to an OR with a range (AND) leaf the compiler's ``_flatten_or`` could
    not classify, so the whole RandSet went uncompiled and deferred.

Each test runs under a no-fallback guard so a regression that re-introduces the
defer fails loudly here. Skipped when the dv-solve native library is unavailable.
See doc/notes/dv_solve_phaseG_primary_completeness_plan.md.
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
    """Make any fall-through to Boolector raise, so a shape that is not handled
    natively by the dv-solve primary engine fails the test."""
    import vsc.model.solver.boolector_backend as bb
    orig = bb.BoolectorBackend.solve_randset

    def _raise(self, rs, *a, **k):
        raise AssertionError(
            "dv-solve fell back to Boolector for a RandSet (not native?)")

    bb.BoolectorBackend.solve_randset = _raise
    try:
        yield
    finally:
        bb.BoolectorBackend.solve_randset = orig


U64_MAX = (1 << 64) - 1


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolvePhaseGNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    # ------------------------------------------------------------------ #
    # G-1 — unsigned-64                                                    #
    # ------------------------------------------------------------------ #
    def test_g1_u64_relational_native(self):
        """`x < y` and `x > 1000` over two u64 fields: native, satisfied."""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.x = vsc.rand_bit_t(64)
                s.y = vsc.rand_bit_t(64)

            @vsc.constraint
            def k(s):
                s.x < s.y
                s.x > 1000
        obj = c()
        random.seed(0)
        with _no_fallback():
            for _ in range(200):
                obj.randomize()
                self.assertLess(int(obj.x), int(obj.y))
                self.assertGreater(int(obj.x), 1000)

    def test_g1_u64_upper_half_native(self):
        """Relational solving reaches the unsigned upper half ``[2**63, 2**64-1]``
        natively (the signed-int64 "2**63 cliff" is gone): over ``x < y`` on two
        u64 fields, values routinely exceed 2**63 with no fallback and no
        violation.  (NB: a *literal* constant bound in the upper half, e.g.
        ``x > (1<<63)``, still defers — a separate pyvsc literal-width inference
        edge, not the C comparator path; the defer is sound via BV-SAT.)"""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.x = vsc.rand_bit_t(64)
                s.y = vsc.rand_bit_t(64)

            @vsc.constraint
            def k(s):
                s.x < s.y
        obj = c()
        random.seed(0)
        upper = 0
        with _no_fallback():
            for _ in range(400):
                obj.randomize()
                x, y = int(obj.x), int(obj.y)
                self.assertLess(x, y)
                self.assertLessEqual(y, U64_MAX)
                if x > (1 << 63) or y > (1 << 63):
                    upper += 1
        self.assertGreater(
            upper, 50, "upper half never reached natively (%d/400)" % upper)

    def test_g1_u64_distribution_spreads(self):
        """A free-ish u64 (`x > 1000`) spreads across the full 64-bit range, not
        clustered in the low/ signed-positive half."""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.x = vsc.rand_bit_t(64)

            @vsc.constraint
            def k(s):
                s.x > 1000
        obj = c()
        random.seed(1)
        buckets = [0] * 8
        with _no_fallback():
            for _ in range(2000):
                obj.randomize()
                buckets[int(obj.x) >> 61] += 1
        # Every octant of [0, 2**64) should get a healthy share (ideal ~250).
        for i, b in enumerate(buckets):
            self.assertGreater(
                b, 120, "octant %d under-sampled: %s" % (i, buckets))

    # ------------------------------------------------------------------ #
    # G-2 — multi-range membership                                         #
    # ------------------------------------------------------------------ #
    def test_g2_multi_range_inside_native(self):
        """`a inside {1,2} U [100,200]` (a gap) solves natively and respects
        membership — previously deferred via the OR-of-ranges encoding."""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(32)

            @vsc.constraint
            def k(s):
                s.a.inside(vsc.rangelist(1, 2, (100, 200)))
        obj = c()
        random.seed(0)
        seen = set()
        with _no_fallback():
            for _ in range(400):
                obj.randomize()
                a = int(obj.a)
                self.assertTrue(a in (1, 2) or 100 <= a <= 200,
                                "a=%d outside {1,2} U [100,200]" % a)
                seen.add(a)
        # Coverage: both sub-ranges must be exercised (not collapsed to one).
        self.assertTrue(seen & {1, 2}, "low sub-range never hit")
        self.assertTrue(any(100 <= a <= 200 for a in seen),
                        "high sub-range never hit")

    def test_g2_multi_range_with_relation_native(self):
        """Multi-range membership combined with a cross-field relation."""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(32)
                s.b = vsc.rand_bit_t(32)

            @vsc.constraint
            def k(s):
                s.a.inside(vsc.rangelist(1, 2, (100, 200)))
                s.a < s.b
        obj = c()
        random.seed(0)
        with _no_fallback():
            for _ in range(300):
                obj.randomize()
                a = int(obj.a)
                self.assertTrue(a in (1, 2) or 100 <= a <= 200)
                self.assertLess(a, int(obj.b))

    def test_g2_gap_forced_unsat(self):
        """Forcing the value into the gap is UNSAT — the membership propagator
        must reject it (soundness), not silently emit a gap value."""
        @vsc.randobj
        class c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(32)

            @vsc.constraint
            def k(s):
                s.a.inside(vsc.rangelist(1, 2, (100, 200)))
                s.a == 50          # 50 is in the gap -> no solution
        obj = c()
        with self.assertRaises(Exception):
            obj.randomize()


if __name__ == "__main__":
    unittest.main()
