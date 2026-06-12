"""Phase E / P0-T — the dv-solve fallback histogram dashboard.

This is the burn-down dashboard *and* the regression guard for dv-solve
self-sufficiency. It runs a representative corpus of randomizations under
``VSC_SOLVER=dv-solve`` with the always-on fallback tally
(``randomizer.record_fallback``) collecting every ``BackendIncomplete`` deferral
by reason code, then asserts the resulting histogram against a **documented
allowlist**.

It fails loudly on:
  * a *new* reason code (an undocumented defer crept in),
  * a *correctness* reason code being non-zero (``search-incomplete`` /
    ``bvsat-undecided`` mean dv-solve could neither solve nor decide a problem it
    accepted — a bug, not a feature gap),
  * a count regression on a shape an earlier phase drove native (the native
    corpus must produce *zero* fallbacks).

The corpus is split:
  * ``_native_corpus`` — shapes dv-solve handles natively today; **must** defer
    nothing.
  * ``_residual_corpus`` — shapes that *consciously* defer to the Boolector net,
    each tagged with the reason code it is expected to raise (the §5 residue of
    the Phase B/C/D plans). The dashboard's allowlist is exactly this set.

Run standalone to print the live histogram:

    python ve/unit/test_dvsolve_fallback_histogram.py

See doc/notes/dv_solve_phaseE_selfsufficiency_plan.md (E0). Skipped when the
dv-solve native library is unavailable.
"""
import os
import random
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


# Reason codes that signal a *bug*, not a feature gap: dv-solve accepted a
# problem it could neither solve nor authoritatively decide. These must be zero
# on the corpus (both the served and ":hard" re-raised variants).
_CORRECTNESS_CODES = ("search-incomplete", "bvsat-undecided")

# The documented residual allowlist: reason codes dv-solve may *consciously*
# defer to the Boolector net. Keep this in sync with the §5 residual table in
# doc/notes/dv_solve_phaseE_selfsufficiency_plan.md and solver_backends.rst.
_RESIDUAL_ALLOWLIST = {
    "width",        # field width > 255 bits (uint8 add_var width) — permanent
    "dist",         # >64-bit dist / conditional / multiple-dist-on-field
    "array",        # n>64 select, >64 summands, wide aggregate, object randsz
    "unsat-defer",  # width-range UNSAT the primary won't declare authoritatively
}


@contextmanager
def _tally():
    """Enable the always-on fallback tally for the duration of the block and
    yield a function that returns the accumulated histogram."""
    saved = rnd.set_fallback_tally(True)
    rnd.reset_fallback_tally()
    try:
        yield rnd.get_fallback_tally
    finally:
        rnd.reset_fallback_tally()
        rnd.set_fallback_tally(saved)


# --------------------------------------------------------------------------- #
# Corpus                                                                        #
# --------------------------------------------------------------------------- #
# Each corpus entry is (label, factory) where factory() returns a fresh randobj
# instance. The dashboard randomizes each a handful of times.

def _native_corpus():
    """Shapes dv-solve handles natively today — must defer *nothing*."""

    @vsc.randobj
    class Scalar(object):
        def __init__(s):
            s.a = vsc.rand_uint8_t()
            s.b = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            s.a < s.b
            s.b < 200

    @vsc.randobj
    class Dist(object):
        def __init__(s):
            s.a = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            vsc.dist(s.a, [vsc.weight((1, 3), 1), vsc.weight((200, 255), 2)])

    @vsc.randobj
    class FixedArraySum(object):
        def __init__(s):
            s.arr = vsc.rand_list_t(vsc.uint8_t(), 4)
        @vsc.constraint
        def c(s):
            s.arr.sum < 200
            with vsc.foreach(s.arr) as e:
                e > 0

    @vsc.randobj
    class RandSzArray(object):
        def __init__(s):
            s.arr = vsc.randsz_list_t(vsc.uint16_t())
        @vsc.constraint
        def sc(s):
            s.arr.size.inside(vsc.rangelist(0, 1, 2, 4, 8))
        @vsc.constraint
        def vc(s):
            with vsc.foreach(s.arr, idx=True) as idx:
                s.arr[idx] == idx

    @vsc.randobj
    class Wide128(object):
        # Wide field with a sub-int64 bound: representable through add_var's
        # int64 envelope, so dv-solve handles it natively (Phase D). A wide
        # field whose bound exceeds int64 (e.g. ``a > (1<<63)``) defers with
        # ``unsat-defer`` instead — a documented residual, see Phase E §5.
        def __init__(s):
            s.a = vsc.rand_bit_t(128)
        @vsc.constraint
        def c(s):
            s.a < 1000000

    return [
        ("scalar", Scalar),
        ("dist", Dist),
        ("fixed_array_sum", FixedArraySum),
        ("randsz_array", RandSzArray),
        ("wide_128", Wide128),
    ]


def _residual_corpus():
    """Shapes that *consciously* defer to the Boolector net, each tagged with the
    reason code it is expected to raise. The dashboard asserts these defer (and
    only with these codes)."""

    @vsc.randobj
    class Width256(object):
        # > 255 bits: add_var width is a uint8 → permanent residual ("width").
        def __init__(s):
            s.a = vsc.rand_bit_t(256)
        @vsc.constraint
        def c(s):
            s.a > 1

    @vsc.randobj
    class WideDist(object):
        # dist on a > 64-bit field → not natively encodable ("dist").
        def __init__(s):
            s.a = vsc.rand_bit_t(96)
        @vsc.constraint
        def c(s):
            vsc.dist(s.a, [vsc.weight((1, 3), 1),
                           vsc.weight(((1 << 80), (1 << 80) + 5), 2)])

    return [
        ("width256", "width", Width256),
        ("wide_dist", "dist", WideDist),
    ]


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveFallbackHistogram(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _run(self, factory, n=8, seed=0):
        random.seed(seed)
        obj = factory()
        for _ in range(n):
            obj.randomize()

    # ------------------------------------------------------------------ #
    # T-E0a — the native corpus must defer NOTHING                         #
    # ------------------------------------------------------------------ #
    def test_native_corpus_no_fallback(self):
        with _tally() as tally:
            for label, factory in _native_corpus():
                self._run(factory)
            hist = tally()
        self.assertEqual(
            hist, {},
            "native corpus produced fallbacks (should be zero): %s" % hist)

    # ------------------------------------------------------------------ #
    # T-E0b — each residual shape defers with its documented reason code   #
    # ------------------------------------------------------------------ #
    def test_residual_corpus_reason_codes(self):
        for label, expect_code, factory in _residual_corpus():
            with _tally() as tally:
                self._run(factory, n=2)
                hist = tally()
            codes = {k.split(":")[0] for k in hist}
            self.assertIn(
                expect_code, codes,
                "residual shape '%s' did not defer with reason_code=%r; got %s"
                % (label, expect_code, hist))
            self.assertTrue(
                codes <= _RESIDUAL_ALLOWLIST,
                "residual shape '%s' deferred with an undocumented reason code: "
                "%s (allowed: %s)" % (label, codes - _RESIDUAL_ALLOWLIST,
                                      _RESIDUAL_ALLOWLIST))

    # ------------------------------------------------------------------ #
    # T-E0c — the dashboard: full corpus histogram vs the allowlist        #
    # ------------------------------------------------------------------ #
    def test_histogram_dashboard(self):
        with _tally() as tally:
            for label, factory in _native_corpus():
                self._run(factory)
            for label, _code, factory in _residual_corpus():
                self._run(factory, n=2)
            hist = tally()

        self._emit(hist)

        # (i) no correctness code may appear (bug, not a feature gap)
        for code in _CORRECTNESS_CODES:
            for key in (code, "%s:hard" % code):
                self.assertNotIn(
                    key, hist,
                    "correctness reason code %r is non-zero (%d) — dv-solve "
                    "accepted a problem it could not solve/decide: %s"
                    % (key, hist.get(key, 0), hist))

        # (ii) every observed reason code must be on the documented allowlist
        observed = {k.split(":")[0] for k in hist}
        undocumented = observed - _RESIDUAL_ALLOWLIST
        self.assertEqual(
            undocumented, set(),
            "undocumented fallback reason code(s) %s in histogram %s — add a "
            "native encoding or a documented-residual row (see Phase E §5)."
            % (undocumented, hist))

    @staticmethod
    def _emit(hist):
        """Print the histogram so the burn-down is visible in CI logs."""
        print("\n=== dv-solve fallback histogram ===")
        if not hist:
            print("  (no fallbacks)")
        else:
            for key in sorted(hist):
                print("  %-24s %d" % (key, hist[key]))
        print("===================================")


if __name__ == "__main__":
    # Standalone: print the live histogram over the corpus, no assertions.
    if not _dvsolve_available():
        raise SystemExit("dv-solve native library not available")
    ctor.set_solver_backend("dv-solve")
    with _tally() as tally:
        for _label, factory in _native_corpus():
            random.seed(0)
            obj = factory()
            for _ in range(8):
                obj.randomize()
        for _label, _code, factory in _residual_corpus():
            random.seed(0)
            obj = factory()
            for _ in range(2):
                obj.randomize()
        TestDvSolveFallbackHistogram._emit(tally())
