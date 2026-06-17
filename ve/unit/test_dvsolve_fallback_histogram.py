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
# on the corpus (both the served and ":hard" re-raised variants). Note
# `bvsat-undecided` here means a *genuine* BV-SAT UNKNOWN/ERROR — the case where
# BV-SAT proves SAT but defers for distribution/solve_order is the separate,
# expected `bvsat-sat-deferred` residual (F-E1), not a correctness signal.
_CORRECTNESS_CODES = ("search-incomplete", "bvsat-undecided")

# The documented residual allowlist: reason codes dv-solve may *consciously*
# defer to the Boolector net. Keep this in sync with the §5 residual table in
# doc/notes/dv_solve_phaseE_selfsufficiency_plan.md and solver_backends.rst.
_RESIDUAL_ALLOWLIST = {
    "width",        # field width > 255 bits (uint8 add_var width) — permanent
    "dist",         # >64-bit dist / conditional / multiple-dist-on-field
    "array",        # n>64 select, >64 summands, wide aggregate, object randsz
    "bvsat-sat-deferred",  # primary couldn't decide, BV-SAT *proved SAT*, deferred
                    # to the fallback for distribution / solve_order. Expected,
                    # correct two-engine operation — NOT a completeness gap (F-E1).
    "translator-unsupported",  # a constraint/expression node the translator does
                    # not yet encode (e.g. constraint override / inline scope).
                    # Replaces the old default `incomplete` code so every
                    # translator defer is tracked, not catch-all (F-E6).
}

# F-2c — the residual manifest: for each allowlisted reason code, the *product
# sign-off disposition* that gates F-3 (dropping Boolector from the default
# chain). Two dispositions:
#   "permanent" — cannot be made fallback-free with reasonable effort; F-3 keeps
#                 the retained opt-in Boolector fallback reachable for it
#                 (F-3b `_RETAINED_RESIDUAL_CODES`).
#   "closable"  — a known native / wide-encoding path exists (`[dvs]` C-engine or
#                 translator work); tracked for burn-down, served by the net until
#                 then. NOT a correctness gap — see _CORRECTNESS_CODES.
# The keys MUST equal _RESIDUAL_ALLOWLIST (asserted by test_residual_manifest_in_sync)
# so this catalog, the allowlist, the §5 Phase-E residual table, and the F-2c plan
# table cannot drift.
_RESIDUAL_MANIFEST = {
    "width":        ("permanent",
                     "field width > 255 bits — C ABI uint8 add_var width cap"),
    "dist":         ("closable",
                     ">64-bit / conditional / multiple-dist-on-field — [dvs] dist "
                     "composition + wide encode"),
    "array":        ("closable",
                     "Phase C §5 tail after EF-1a closed var-indexed select: "
                     "randsz/co-solved aggregate, >64 element/summand caps — "
                     "[dvs] C work"),
    "translator-unsupported": ("closable",
                     "a constraint/expression node the translator does not yet "
                     "encode — translator coverage"),
    "bvsat-sat-deferred": ("closable",
                     "SAT-proved but not served: an unsigned upper-half constant "
                     "bound (pyvsc literal-width inference, Phase G residual), "
                     "sampler dist-weighting (F-2b), or a >64-bit ordered-field "
                     "freeze (the F-2a wide-order residual)"),
}


@contextmanager
def _tally():
    """Enable the always-on fallback tally for the duration of the block and
    yield a function that returns the accumulated histogram. Snapshots and
    restores the process-global tally so this test's synthetic corpus does not
    corrupt a concurrent suite-wide audit run (F-0a)."""
    snap = rnd.snapshot_fallback_tally()
    rnd.set_fallback_tally(True)
    rnd.reset_fallback_tally()
    try:
        yield rnd.get_fallback_tally
    finally:
        rnd.restore_fallback_tally(snap)


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
        # int64 envelope, so dv-solve handles it natively (Phase D).
        def __init__(s):
            s.a = vsc.rand_bit_t(128)
        @vsc.constraint
        def c(s):
            s.a < 1000000

    @vsc.randobj
    class WideAboveInt64(object):
        # Wide field whose *bound* exceeds the int64 add_var envelope
        # (``a > 2**63`` on a 128-bit field). The field is routed to the
        # width-agnostic BV-SAT engine, which gets the real bound from the
        # translated constraint (a wide >64-bit literal lowered to a limb concat),
        # so dv-solve force-serves it natively — no `wide-range` defer (Phase F).
        def __init__(s):
            s.a = vsc.rand_bit_t(128)
        @vsc.constraint
        def c(s):
            s.a > (1 << 63)

    @vsc.randobj
    class WideEqLiteral(object):
        # Equality against a >64-bit literal, lowered to a concat of limbs and
        # solved natively by BV-SAT (exercises the wide-literal width fix).
        def __init__(s):
            s.a = vsc.rand_bit_t(128)
        @vsc.constraint
        def c(s):
            s.a == 0xDEADBEEFCAFEBABE0123456789ABCDEF

    @vsc.randobj
    class NotInside(object):
        # Negated membership over a contiguous-domain var. The translator lowers
        # `!(x in S)` by De Morgan to a conjunction `x != v` (scalars) / `(x<lo)||
        # (x>hi)` (ranges) — both of which the bounds engine decides natively —
        # instead of `NOT(OR(x==v...))`, which would stall and defer
        # `bvsat-sat-deferred` (the negated-membership burn-down). NB: over an
        # *enum* (gapped) domain it would still defer — that's the separate
        # positive-gapped-membership capability gap, not this.
        def __init__(s):
            s.x = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            s.x.not_inside(vsc.rangelist(0, 1, 2, 3, 5, 6, 7, 8, vsc.rng(100, 120)))

    @vsc.randobj
    class VarIndexedSelect(object):
        # arr[idx] with a *rand* index — variable-indexed array select (the
        # largest `array` residual class, Phase C-1). The translator now encodes
        # it natively as an ITE chain over the active elements (EF-1a), so it
        # defers NOTHING. When the index is co-solved it selects symbolically —
        # which Boolector gets *wrong* (it snapshots the index) — so dv-solve is
        # strictly more correct here; XCHECK still agrees because it validates the
        # finished model, when the index is concrete.
        def __init__(s):
            s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 4)
            s.idx = vsc.rand_uint8_t()
            s.val = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            s.idx < 4
            s.arr[s.idx] == s.val

    @vsc.randobj
    class ImpliesArithGuard(object):
        # Implication guard = logical AND of comparisons over lifted arithmetic
        # (the clog2 idiom). The *primary* bounds engine's disjunction propagation
        # is unsound here, so dv-solve routes the RandSet straight to the complete
        # BV-SAT engine (force-serve) — the encoding is correct and BV-SAT is
        # authoritative — instead of deferring to the fallback. So it defers
        # NOTHING even with serve-SAT off (Phase F / F-2; was an `implies-aux`
        # residual under F-E3).
        def __init__(s):
            s.a = vsc.rand_uint8_t()
            s.b = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            with vsc.implies(((s.b - 1) >= 4) & ((s.b - 1) < 8)):
                s.a == 3

    @vsc.randobj
    class GuardedSoftPrimary(object):
        # A guarded (conditional) soft `if_then(g): soft(e)` with a single-statement
        # body lowers to the disjunction soft `(!g)||e` and is served on the
        # *primary* path: the relaxation loop keeps it and bound-propagation enforces
        # the kept disjunction. Honored natively, defers NOTHING (engine plan DSE-0;
        # the prior "soft-guarded" defer was a pyvsc translator memo-key bug, fixed).
        def __init__(s):
            s.a = vsc.rand_uint8_t()
            s.d = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            s.a > 10
            with vsc.if_then(s.a > 5):
                vsc.soft(s.d == 40)

    @vsc.randobj
    class SoftOnBVSatServe(object):
        # A soft coupled into a RandSet that *force-serves via BV-SAT* (the
        # conjunctive guard body routes it to the complete BV-SAT engine). The
        # serve path runs the engine's soft-aware MaxSAT (zsp_bbsolver_check_maxsat)
        # and the sampler enforces the kept set, so `soft(a==40)` is honored
        # natively — defers NOTHING (engine plan DSE-2). This previously deferred
        # (`soft-serve-deferred`); the unconditional soft on this path was also the
        # latent silent-drop the old `soft-guarded` gate missed.
        def __init__(s):
            s.g = vsc.rand_uint8_t()
            s.a = vsc.rand_uint8_t()
            s.b = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            s.g == 1
            with vsc.if_then(s.g == 1):
                s.a < 200
                s.b < 200
            vsc.soft(s.a == 40)

    @vsc.randobj
    class SoftPriorityLadder(object):
        # A ladder of three mutually-conflicting softs at distinct (declaration-
        # order) priorities. The engine's MaxSAT relaxation keeps the maximal
        # priority-respecting set (the last-declared/highest-preference soft) and
        # relaxes the rest — entirely on the primary path, defers NOTHING. Locks the
        # DSE-3 priority-fidelity surface against a regression that re-introduces a
        # defer (or routes the ladder to the net).
        def __init__(s):
            s.x = vsc.rand_uint8_t()
        @vsc.constraint
        def c(s):
            vsc.soft(s.x == 1)
            vsc.soft(s.x == 2)
            vsc.soft(s.x == 3)

    return [
        ("scalar", Scalar),
        ("dist", Dist),
        ("fixed_array_sum", FixedArraySum),
        ("randsz_array", RandSzArray),
        ("wide_128", Wide128),
        ("wide_above_int64", WideAboveInt64),
        ("wide_eq_literal", WideEqLiteral),
        ("not_inside", NotInside),
        ("var_indexed_select", VarIndexedSelect),
        ("implies_arith_guard", ImpliesArithGuard),
        ("guarded_soft_primary", GuardedSoftPrimary),
        ("soft_on_bvsat_serve", SoftOnBVSatServe),
        ("soft_priority_ladder", SoftPriorityLadder),
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

    @vsc.randobj
    class UpperHalfConstBound(object):
        # `x > 2**63` on an unsigned u64: a *constant* bound in the unsigned upper
        # half. The literal is inferred signed (width 65) and lowered to a concat
        # wide-const the comparison compiler can't fold, so the constraint is left
        # uncompiled and BV-SAT *proves it SAT* — `bvsat-sat-deferred`, served by
        # the net (sound). A pyvsc literal-width inference residual, independent of
        # the C engine (Phase G §"Residual"); the upper half is reachable natively
        # via *relational* constraints. Deterministic (unlike a bitwise search).
        def __init__(s):
            s.x = vsc.rand_bit_t(64)
        @vsc.constraint
        def sc(s):
            s.x > (1 << 63)

    @vsc.randobj
    class OverCapSum(object):
        # An array aggregate (`sum`) over more elements than the native n-ary sum
        # propagator's summand cap (`_MAX_SUM_VARS`=64). The translator defers it
        # ("array"); served by the net. This is the surviving `array` residual
        # tail after EF-1a closed the variable-indexed-select shape (now native).
        def __init__(s):
            s.arr = vsc.rand_list_t(vsc.uint8_t(), 100)
        @vsc.constraint
        def c(s):
            s.arr.sum < 5000
            with vsc.foreach(s.arr) as e:
                e > 0

    return [
        ("width256", "width", Width256),
        ("wide_dist", "dist", WideDist),
        ("upper_half_const_bound", "bvsat-sat-deferred", UpperHalfConstBound),
        ("over_cap_sum", "array", OverCapSum),
    ]


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveFallbackHistogram(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        # The documented residual taxonomy is the *default-config* one (serve-SAT
        # off). Pin it so the dashboard is deterministic even when the ambient env
        # forces serve-SAT on (e.g. a suite-wide audit run): with serve-SAT on,
        # a `bvsat-sat-deferred` shape (e.g. `bitand_eq`) would be *served* by the
        # sampler instead of deferring, which is correct behavior but not what
        # this dashboard documents.
        import vsc.model.solver.dvsolve_backend as _dvb
        self._saved_serve = _dvb._BVSAT_SERVE_SAT_MODE
        _dvb._BVSAT_SERVE_SAT_MODE = "off"

    def tearDown(self):
        import vsc.model.solver.dvsolve_backend as _dvb
        _dvb._BVSAT_SERVE_SAT_MODE = self._saved_serve
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
    # T-E0a' — dynamic-constraint references solve natively (F-E6).         #
    # Exercised via randomize_with (the generic corpus runner only calls    #
    # randomize()), covering the indexed enable, the non-indexed sibling    #
    # combined with `|`, and a dist inside a dynamic block.                 #
    # ------------------------------------------------------------------ #
    def test_dynamic_constraint_native(self):
        @vsc.randobj
        class Dyn(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.constraint
            def a_c(s):
                s.a <= 100
            @vsc.dynamic_constraint
            def a_small(s):
                s.a.inside(vsc.rangelist(vsc.rng(1, 10)))
            @vsc.dynamic_constraint
            def a_large(s):
                s.a.inside(vsc.rangelist(vsc.rng(90, 100)))

        obj = Dyn()
        with _tally() as tally:
            random.seed(0)
            for _ in range(8):
                with obj.randomize_with() as it:
                    it.a_small()
                self.assertTrue(1 <= obj.a <= 10)
                with obj.randomize_with() as it:
                    it.a_small() | it.a_large()
                self.assertTrue(1 <= obj.a <= 10 or 90 <= obj.a <= 100)
            hist = tally()
        self.assertEqual(
            hist, {},
            "dynamic-constraint references produced fallbacks "
            "(should solve natively): %s" % hist)

    def test_dynamic_constraint_soft_correct(self):
        # A `soft` member inside a dynamic block is routed through the RandSet-level
        # soft path (not translated as a hard conjunction), so it is dropped when it
        # conflicts and a valid value is still served. Here soft `a == 5` conflicts
        # with hard `a >= 50`; the result must honor the hard bound, never wrongly
        # force a == 5 or report UNSAT.
        @vsc.randobj
        class DynSoft(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
            @vsc.dynamic_constraint
            def hi_pref5(s):
                s.a >= 50
                s.a <= 100
                vsc.soft(s.a == 5)

        # Isolate the global fallback tally: this shape defers to the net (serve-SAT
        # is off while a fallback is present — the expected two-engine behavior), so
        # without snapshot/restore its `bvsat-sat-deferred` events would leak into
        # the suite-wide self-sufficiency audit and read as a real serving residual.
        with _tally():
            obj = DynSoft()
            for _ in range(4):
                with obj.randomize_with() as it:
                    it.hi_pref5()
                self.assertTrue(
                    50 <= obj.a <= 100,
                    "soft-in-dynamic-block over-constrained: a=%d" % int(obj.a))

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
    # T-F0a / F-2c — the residual manifest is the single source of truth   #
    # ------------------------------------------------------------------ #
    def test_residual_manifest_in_sync(self):
        """The F-2c manifest (reason code → sign-off disposition) must enumerate
        exactly the allowlisted codes — so the catalog, the allowlist, and the
        plan's F-2c table cannot drift. A new defer code with no manifest row (or
        a manifest row for a retired code) breaks here, forcing a conscious
        product decision rather than a silent serving dependency."""
        self.assertEqual(
            set(_RESIDUAL_MANIFEST), _RESIDUAL_ALLOWLIST,
            "residual manifest keys must equal the allowlist; diff: %s"
            % (set(_RESIDUAL_MANIFEST) ^ _RESIDUAL_ALLOWLIST))
        for code, (disp, note) in _RESIDUAL_MANIFEST.items():
            self.assertIn(disp, ("permanent", "closable"),
                          "code %r: unknown disposition %r" % (code, disp))
            self.assertTrue(note, "code %r: missing a sign-off note" % code)
        # No correctness code may ever be classed a residual.
        self.assertEqual(
            set(_RESIDUAL_MANIFEST) & set(_CORRECTNESS_CODES), set(),
            "a correctness code must never appear in the residual manifest")

    def test_residual_corpus_codes_in_manifest(self):
        """Every residual-corpus shape's expected code is catalogued in the
        manifest (the corpus exercises a representative slice of the manifest)."""
        for label, expect_code, _factory in _residual_corpus():
            self.assertIn(
                expect_code, _RESIDUAL_MANIFEST,
                "residual shape '%s' expects code %r with no manifest row"
                % (label, expect_code))

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
