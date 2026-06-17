# dv-solve Test-Suite Enhancement Plan: "Mine the pyvsc Suite for Correctness, Distribution & Performance"

Status: **In progress** (2026-06-17)
Companion to: `dv_solve_feature_completeness_plan.md`, `dv_solve_phaseF_retirement_plan.md`,
`dv_solve_performance_plan.md`, `dv_solve_phaseG_primary_completeness_plan.md`.

> **Progress log** (newest first)
> - **2026-06-17 (later still) — I-1 fix confirmed; A1 done; B-gate landed.**
>   18× full soak after the fix: **pass=18 fail=0** (was ~1/21). **A1 done:** added 15
>   constraint-relevant suites (implies, if_else, in, unique, rangelist_bug,
>   constraint_mode, rand_mode, override, list_scalar/object, compound_obj, partselect,
>   select, width_masking, types) to `ve/xcheck_corpus.txt`; expanded corpus runs
>   **clean under XCHECK (211 tests, 0 mismatches)**; manifest test green; 6× repeat in
>   progress. Added integration-level `ve/unit/test_dvsolve_soft_soundness.py` (flat
>   independent-soft, priority, determinism — pass on BOTH backends, confirming the
>   invariants are real). dvsolve native suite **96 passed**. *Clarification while
>   building it:* the `test_soft_nested` *bundled-block* shape (several softs in one
>   guarded `if_then`, one conflicting) drops the independent softs **identically on
>   Boolector** and is seed-dependent — that is pyvsc front-end soft-bundle lowering,
>   NOT a dv-solve soundness property, so it is not asserted as a per-soft invariant.
>   The dv-solve-specific bug was strictly the *flat primary relaxation* (I-1), now fixed
>   and locked by the C test.
> - **2026-06-17 (later) — root-caused and FIXED the soft-soundness bug (I-1).**
>   Traced to the primary engine's *subtractive* MaxSAT relaxation in
>   `zsp_search.c` (`solver_solve`): to reach a conflicting higher-preference soft
>   it walks down the priority order dropping lower-preference softs, shedding
>   satisfiable ones as collateral and returning `SOLVE_OK` with them violated.
>   Built a **deterministic C-level repro** (`packages/dv-solve/tests/unit/test_soft.py::
>   test_soft_no_collateral_drop_primary`: hard `x==20`; softs `a==11@0, x==5@1,
>   d==40@2` → bug returned `d=62`). Fixed with an **additive re-add refinement**:
>   after the subtractive loop reaches SAT (only when a relaxation occurred), re-add
>   each dropped soft highest-preference-first, committing any that keeps the problem
>   SAT — making the primary keep the same maximal set the BV-SAT serve path already
>   keeps (primary == serve). It never enters the all-pinned-to-0 state, sidestepping
>   the quirk that blocked a from-scratch additive primary (the reason DSE-3 left the
>   subtractive form in place). Validation: new repro passes; full C unit suite
>   **523 passed**; `ve/unit` + `ve/unit_dc` soft suites green under XCHECK; 18× soak
>   re-run in progress to confirm the end-to-end flake is gone. The `!=`-soft path
>   has a separate, escalation-covered limitation (compile-time tightening doesn't
>   fully undo on relaxation → spurious primary UNSAT → handled by BV-SAT escalation),
>   noted but not in scope here.
> - **2026-06-17 — baseline soak surfaced a real cross-process nondeterminism.**
>   Running the *current* 22-file XCHECK corpus (`ve/run_xcheck_soak.sh`) failed at
>   `test_constraint_soft.py::test_soft_nested` (`nested.d == 40` came back `10`).
>   The soft `d == 40` is **independent of every hard constraint and every other
>   soft** — a maximal priority-respecting soft set *must* keep it, and Boolector
>   always does. dv-solve drops it only intermittently. Characterization so far:
>     - Standalone (`o.randomize()` ×5000 in one process): **never** dropped.
>     - Whole `test_constraint_soft.py` alone, all backends: **passes**.
>     - Full soak: dropped in some runs, not others — i.e. **flaky across processes,
>       stable within a process**. That signature points to **pointer/heap-address
>       ordering** in the engine's soft-selection (ASLR-dependent), *not* anything
>       controlled by pyvsc's `random.seed(0)`. Confirming with an `setarch -R`
>       (ASLR-off) soak and quantifying the per-run failure rate.
>   This is exactly the class of defect Workstreams A (differential soak) and B4
>   (determinism lock) exist to catch, and it gates A1: a flaky member makes the
>   soak gate itself flaky, so it must be fixed or quarantined before the corpus
>   is widened. Tracked in §7.

---

## 1. Premise

dv-solve is **functionally complete and XCHECK-clean**: full `ve/unit` (499) and
`ve/unit_dc` (106) pass under `VSC_SOLVER=dv-solve` and under `VSC_DVSOLVE_XCHECK=1`
with **0 mismatches**; both correctness reason codes are 0 suite-wide; native serving
covers every feature area with only 2 sound residuals (>255-bit `width`, nested-soft
`translator-unsupported`). The remaining work is **adoption-window confidence**, not
feature work — and the cheapest, highest-signal way to build that confidence is to
turn the **existing pyvsc unit suite into a systematic dv-solve verification corpus**
rather than authoring more hand-written one-offs.

This plan is **test-only**. It does not change solver behavior. It identifies where
the pyvsc suite already exercises constraint shapes that dv-solve's dedicated tests
do *not* cover, and wires those shapes into three durable gates: **correctness
(differential)**, **distribution quality (statistical)**, and **performance
(regression floor)**.

### What exists today (baseline)

- **12 dv-solve native test files** (`ve/unit/test_dvsolve_*.py`) — per-phase
  coverage (dist, arrays, array-select, soft, phaseG, solve-order, wide, serve-sat,
  fallback-histogram, lib-load) using *no-fallback guards* (prove native serving) and
  *direct XCHECK* (prove soundness). ~100 scenarios total.
- **XCHECK differential harness** (`src/vsc/model/solver/xcheck.py`) — re-checks every
  dv-solve model against a Boolector-built formula (verdict + membership). Strided
  sampling supported (rate 1.0/0.5/0.25).
- **Soak corpus** (`ve/xcheck_corpus.txt`, 22 targets) + `ve/run_xcheck_soak.sh` — the
  F-4 default-flip gate. Real-workload functional suites run under XCHECK.
- **Distribution scoring** (`ve/unit/distribution_score.py`) — `score(values, feasible)`
  → reduced chi-square, chi2 survival p-value, coverage fraction, coupon-collector
  ratio. No scipy. Used by `test_distribution_quality.py` (1 test) + the dist-native
  tests.
- **Fallback tally dashboard** (`conftest.py` + `VSC_DVSOLVE_FALLBACK_TALLY=1`) —
  suite-wide deferral histogram with allowlist gate (`test_dvsolve_fallback_histogram.py`).
- **Cross-frontend benchmark** (`benchmarks/bench_frontends.py` + `RESULTS.md`) — manual
  throughput harness across {classic,dc} × {dv-solve,boolector} × 6 workloads. **Not a
  test** — no regression gate.
- **dc front-end equivalence harness** (`ve/unit_dc/test_xcheck_frontends.py`) — proves
  classic ≡ dataclass behaviorally over a scalar corpus.

---

## 2. Gap analysis — what the pyvsc suite covers that dv-solve gates do not

The pyvsc suite has **~305 constraint-solving test methods across ~40 files**. The
dv-solve soak corpus only pulls in **22 files**, and several constraint-heavy files
that exercise shapes *known to have been historically buggy* (signed compare, bitwise
invert, inside-with-gaps) are **absent from the corpus**, meaning they never run under
XCHECK in the soak gate. Three categories of gap:

### 2.1 Correctness (differential) gaps — files NOT in the XCHECK soak corpus

These contain real constraint shapes but are not in `ve/xcheck_corpus.txt`, so they are
not re-checked against Boolector in the soak gate:

| File | Shapes exercised | Why it matters for dv-solve |
|------|------------------|------------------------------|
| `test_implies.py`, `test_if_else.py` | implication / if-else-elseif chains, `inside` in guards | conjunctive-body reification (the G-1 reification bug lived here) |
| `test_in.py` | `inside` over rangelists, dynamic ranges, discrete sets, nested ranges | multi-range membership + gap soundness (G-2 area) |
| `test_unique.py` | `unique()` over many vars, stress | pairwise-`!=` encoding correctness |
| `test_constraint_rangelist*.py` | mutable rangelists, UNSAT detection | rangelist lowering + UNSAT authority |
| `test_constraint_mode.py`, `test_rand_mode.py` | enable/disable constraints & fields, bounds recompute | plan-cache invalidation correctness |
| `test_constraint_override.py` | inheritance override | constraint-set resolution |
| `test_list_scalar.py`, `test_list_object.py` | randsz lists, object lists, cross-field constraints | array element solving beyond the array-native set |
| `test_compound_obj.py` (25), `test_segmented_randomization.py` | nested rand_attr objects | nested-model traversal under native serving |
| `test_partselect.py`, `test_select.py` | bit-slice writes, distselect/randselect | partselect lowering |
| `test_width_masking.py`, `test_types.py` | width truncation, signed/unsigned | value masking / sign correctness |
| `test_constraint_failure.py`, `test_solve_failure.py` | UNSAT diagnostics, enum conflicts | **UNSAT verdict parity** (dv-solve is the UNSAT authority) |
| `test_solver_conformance.py` (25) | broad per-feature SAT verification | already backend-parameterized — should be XCHECK-gated |
| **entire `ve/unit_dc/` suite** | dataclass front-end | dc path never runs under the XCHECK soak corpus |

### 2.2 Distribution-quality gaps

Quantitative distribution scoring exists but is applied narrowly:

- `test_distribution_quality.py` scores **one** scenario (boolector vs dv-solve uniformity).
- `test_random_dist.py` (23 tests) and `test_constraint_dist.py` (17) build histograms but
  assert **membership / non-emptiness**, not statistical quality, and do not compare
  dv-solve's distribution against the reference.
- The dist-native tests score weighted `dist`, but **plain unconstrained / range-constrained
  uniformity** (the common case) is not systematically scored on the native path.
- No coverage of **distribution under solve_order** (order changes the marginal
  distribution — only 1 native test asserts the semantic, none score the shape) or
  **distribution under soft-constraint relaxation**.

### 2.3 Performance-regression gaps

- `benchmarks/bench_frontends.py` is a **manual** harness; nothing fails CI if dv-solve
  throughput regresses or a workload silently reverts to Boolector fallback.
- `test_perf.py` is a single smoke loop, backend-agnostic, with no assertion.
- The Phase-G win ("dv-solve fastest on all 6 workloads", geo-mean 20.9×) and the
  performance-plan's "compile once" wins have **no guard** — a regression would only be
  caught by re-running the benchmark by hand.
- No gate ties **fallback count** to performance: a workload that starts deferring to
  Boolector is both a correctness-surface and a perf regression, but only the histogram
  test would catch it (and only for its fixed corpus).

---

## 3. Workstreams

### Workstream A — Correctness: widen the differential net

**A1. Grow the XCHECK soak corpus to the full constraint-relevant suite.**
Add the §2.1 files to `ve/xcheck_corpus.txt` (keeping the deliberate exclusions:
dv-solve meta-tests, pure-stat/infra suites). Target: every file that builds a real
constraint and isn't a meta-test runs under `VSC_DVSOLVE_XCHECK=1` in the soak gate.
`test_dvsolve_xcheck_corpus.py` already validates the manifest can't rot.
*Acceptance:* `ve/run_xcheck_soak.sh` green with the expanded corpus; record the new
target count.

**A2. Add a dataclass soak corpus + runner.** Create `ve/xcheck_corpus_dc.txt` covering
the constraint-relevant `ve/unit_dc/` files, and extend `run_xcheck_soak.sh` (or add a
sibling) to run it. Closes the "dc path never soaked under XCHECK" gap.
*Acceptance:* dc corpus green under XCHECK; manifest validated by a dc analogue of the
corpus test.

**A3. Parameterize `test_solver_conformance.py` under XCHECK as a first-class gate.**
It already verifies per-feature SAT across backends; ensure it runs with XCHECK on so
each conformance case is also membership-checked, and add the historically-buggy shapes
(signed compare, bitwise invert, `inside` with gaps) explicitly if absent.

**A4. UNSAT-parity sweep.** dv-solve is the UNSAT authority (Phase A). Add a focused test
that runs every UNSAT/`SolveFailure` scenario in `test_constraint_failure.py`,
`test_solve_failure.py`, `test_constraint_rangelist_bug.py` under dv-solve and asserts
verdict parity with Boolector (both UNSAT, same diagnostic surface). This is the one area
where membership-checking is moot, so verdict-parity is the right gate.

### Workstream B — Distribution quality: systematic scoring

**B1. Generalize the scoring harness into a reusable parametric gate.** Build
`ve/unit/test_dvsolve_distribution_quality.py` that, for a table of (class, feasible-set)
scenarios, draws N samples on dv-solve and asserts: (a) membership 100%, (b) reduced
chi-square / p-value within a uniform-consistent band, (c) coverage ≥ coupon-collector
expectation, and (d) **no worse than Boolector** on the same scenario (the parity bar the
dist-native tests already use for weighted dist, extended to the unconstrained/range
cases). Reuse `distribution_score.score`.
*Scenarios:* plain unconstrained small field, single range, gapped multi-range
(`inside`), enum domain, two co-constrained vars (`a<b`), array element marginal.

**B2. Distribution under weighting — broaden beyond the existing dist-native cases.**
Score per-value `:=` and per-range `:/` bias ratios against their target weights
(observed ratio within tolerance of declared ratio), across static + dynamic weights and
conditional/guarded dist. Much of `test_constraint_dist.py` / `test_random_dist.py` can be
re-expressed as scored assertions instead of membership-only.

**B3. Distribution under solve_order and soft relaxation.** Add scored tests that the
marginal distribution of an order-dependent shape (e.g. `c==0 -> a==0`, solve `a` first)
matches the staged-sampling expectation, and that soft-relaxation frequency (how often a
soft is dropped under conflict) is reasonable. These shapes have semantic tests but no
distribution gate.

**B4. Determinism lock.** Extend the existing per-seed determinism checks to all B1–B3
scenarios: same seed → identical value stream (guards against non-deterministic solver
or sampler changes silently shifting distributions).

### Workstream C — Performance: regression floor

**C1. Promote the benchmark into an assertion-bearing test.** Wrap a trimmed
`bench_frontends.py` workload set in `ve/unit/test_dvsolve_perf_floor.py` (marked slow /
opt-in via env, e.g. `VSC_DVSOLVE_PERF=1`, so it doesn't slow normal CI). Assert
**relative** floors that are machine-independent and durable:
  - dv-solve native-path solves/sec ≥ a fraction of a warm-cache baseline captured in the
    test (ratios, not absolutes — per the perf-plan philosophy).
  - dv-solve ≥ Boolector on the workloads where Phase G established a win (wide64, alu),
    with margin headroom so noise doesn't flake it.
*Acceptance:* test passes on the dev machine; documents the baseline ratios it enforces.

**C2. Zero-fallback performance guard.** For each perf workload, assert the fallback tally
is **0** after the run (a silent revert to Boolector is the most likely perf regression and
is exactly what the histogram test catches for its corpus — extend the principle to the
perf workloads). This ties C to A: a perf regression that is actually a correctness-surface
regression fails loudly.

**C3. Compile-once / plan-cache regression check.** The perf plan's headline is "build +
compile once, re-solve many" (11.4× native-side). Add a test that repeated `randomize()`
on one object reuses the cached plan (assert plan-cache hit count grows, rebuild count
stays flat) so the cache invalidation logic can't silently regress to rebuild-every-call.

---

## 4. Sequencing & effort

| Step | Workstream | Effort | Risk | Payoff |
|------|-----------|--------|------|--------|
| A1 — expand soak corpus | A | low | low | high (immediate differential coverage of historically-buggy shapes) |
| A4 — UNSAT-parity sweep | A | low | low | high (UNSAT authority is high-stakes) |
| B1 — generalized distribution gate | B | med | low | high (closes the biggest stat gap) |
| C2 — zero-fallback perf guard | C | low | low | med (cheap, ties perf↔correctness) |
| A2/A3 — dc soak + conformance XCHECK | A | med | low | med |
| B2/B3 — weighting + order/soft distribution | B | med | med | med |
| C1/C3 — perf floor + plan-cache guard | C | med | med | med (flake risk — keep ratios, opt-in) |
| B4 — determinism locks | B | low | low | med |

**Recommended first slice (highest signal / lowest risk):** A1 + A4 + B1 + C2. These
four are mostly wiring existing infrastructure (corpus manifest, XCHECK harness, scoring
function, fallback tally) to shapes the suite already contains.

**Status of the first slice (2026-06-17):**
- **A1 — DONE.** 15 constraint-relevant suites added to `ve/xcheck_corpus.txt`; expanded
  corpus XCHECK-clean across 1 + 6 repeat runs (211 tests, 0 mismatches); manifest test
  green. Unblocked by the I-1 fix (§7), validated by an 18× soak (pass=18 fail=0).
- **A4 — DONE.** `ve/unit/test_dvsolve_unsat_parity.py`: 5 infeasible shapes
  (range/pair-cycle/inside-gap/eq-contradiction/unique) + SAT controls; dv-solve UNSAT
  verdict must match Boolector. Passing.
- **Bonus — soft-soundness gate.** `ve/unit/test_dvsolve_soft_soundness.py` (flat
  independent-soft, priority, determinism) — passes on both backends. The C-level
  deterministic lock for I-1 lives in the nested `packages/dv-solve` repo
  (`tests/unit/test_soft.py::test_soft_no_collateral_drop_primary`).
- **B1 / C2 — NOT YET.** B1 (distribution gate) is partially pre-covered by
  `test_distribution_quality.py` (4 scored scenarios, no-worse-than-Boolector); remaining
  work is the enum / array-element / weighted-ratio extensions. C2 (zero-fallback perf
  guard) is partially pre-covered by `test_dvsolve_fallback_histogram.py`; remaining work
  is extending the principle to the perf workloads.

> **Where the changes live:** the corpus, the two new pyvsc tests, and this plan are in
> the top-level pyvsc repo. The **C-engine fix + its C regression test are in the nested
> `packages/dv-solve` git repo** (`src/c/zsp_search.c`, `tests/unit/test_soft.py`) — a
> separate working tree, so it needs its own commit.

---

## 5. Acceptance gates (suite-wide, post-enhancement)

1. Expanded `ve/run_xcheck_soak.sh` (classic + dc corpora): **0 XCHECK mismatches**.
2. Distribution gate: all scored scenarios uniform-consistent and **no worse than
   Boolector**; weighted-dist observed ratios within tolerance of declared ratios.
3. Perf floor (opt-in): dv-solve meets the documented relative floors and **0 fallback
   events** on all perf workloads.
4. Determinism: identical value streams per seed across all scored scenarios.
5. No regression in the existing 12 dv-solve native files or the fallback histogram
   allowlist.

---

## 6. Explicit non-goals

- No solver/engine behavior changes — test-only.
- No new feature serving (the 2 sound residuals stay residuals; this plan does not try to
  close `width`>255 or nested-soft).
- No absolute-throughput assertions (machine-dependent; ratios only).
- Not re-testing functional coverage / covergroup machinery (out of scope — solving only).

---

## 7. Discovered issues (tracking)

### I-1 — `test_soft_nested` drops an independent satisfiable soft (cross-process flake)

**Status:** FIXED & VALIDATED (2026-06-17) — additive re-add refinement in `zsp_search.c`;
locked by the deterministic C test `test_soft_no_collateral_drop_primary` (was `d=62`, now
correct); C unit suite 523 passed; 18× post-fix soak **pass=18 fail=0** (was ~1/21).
**Severity:** soundness (rare) + was a soak-gate blocker for A1 (now unblocked).

**Symptom.** `ve/run_xcheck_soak.sh` (current 22-file corpus) intermittently fails
`test_constraint_soft.py::TestConstraintSoft::test_soft_nested`: `nested.d` is `10`
instead of `40`. The constraint declares `soft(self.d == 40)` nested three levels deep
(`implies` → `if_then(a>5)` → `if_then(a>10)`). `d` appears in no hard constraint and no
other soft, so it is independent and trivially satisfiable; a maximal priority-respecting
soft set must keep it. Boolector keeps it 100% of the time.

**Characterization.**
| context | result |
|---|---|
| `o.randomize()` ×5000, single process, auto + serve-sat | never dropped |
| whole `test_constraint_soft.py` alone (dv-solve, boolector, +XCHECK) | always passes |
| corpus prefix files 1–9 in order | passes |
| full 22-file soak | drops in *some* process invocations |

The within-process stability + across-process flakiness is the fingerprint of
**heap-address / pointer-ordering nondeterminism** in the engine's soft-selection
(`maxsat_keepset` / the primary relaxation loop), surfacing only for certain ASLR layouts
once the whole-corpus heap state precedes this solve. It is **not** governed by
`random.seed(0)` (which is reset per test). *(Confirmation via `setarch -R` soak + a
per-run failure-rate count in progress.)*

**Implications for this plan.**
- **A1 is blocked on it:** widening the corpus while a member flakes makes the soak gate
  itself flaky. Fix-or-quarantine first.
- It is the **headline justification for B4 (determinism lock)** and argues that the
  determinism gate must run **cross-process** (repeat the corpus N times / vary layout),
  not just as a single in-process pytest assertion — an in-process loop does **not**
  reproduce it.
- Root-causing/fixing the engine ordering is a C-engine change (notionally outside the
  "test-only" non-goal); if confirmed, file it as a separate solver fix and keep this plan's
  scope to the *gate* that catches it. Decision pending the confirmation run.
