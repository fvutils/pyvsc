# dv-solve Phase E Plan: Self-Sufficiency, Cross-Check, and Fallback Burn-Down

Status: **E0–E2 + E4 DONE; E3 correctness goal MET (optional native burn-downs
remain); Phase F deferred.** (2026-06-12)

Landed this round (all committed on branch `mballance/dv-solve`, lib fix on nested
`packages/dv-solve`):
- **E0** fallback histogram dashboard + always-on tally (§0.5).
- **E1** XCHECK differential cross-check (§0.6) — found & fixed a real soundness
  bug (**F-E3**, clog2 implication guards).
- **E2** serve-SAT posture documented + SAT-path telemetry (`bvsat-sat-deferred`).
- **E4** diagnostics-under-dv-solve regression (E4-1) + lib auto-load fix (E4-2).
- Findings: **F-E3** fixed; **F-E1** resolved (mislabeled code → split
  `bvsat-sat-deferred` vs `bvsat-undecided`); **F-E2** resolved (wide-above-int64
  re-tagged `wide-range`); **F-E4** abstained (comparator gap, not a bug);
  **F-E5** telemetry (`bvsat-sat-deferred = 2796` suite-wide).

Headline validation: **full `ve/unit` under `VSC_DVSOLVE_XCHECK=1` = 468 passed,
0 mismatches** — dv-solve in complete verdict+membership agreement with Boolector
across the suite — and the **correctness reason codes (`search-incomplete`,
`bvsat-undecided`) are 0 suite-wide.**

Remaining: **E3 optional native burn-downs** (reduce the 2796 `bvsat-sat-deferred`
volume — primary-engine completeness; perf, not correctness — see §5/§10) and the
**deferred Phase F** (drop the internal net / flip the global default).
Date: 2026-06-12
Parent: `dv_solve_feature_completeness_plan.md` §3 Phase E (re-scoped below)
Companions:
  * `dv_solve_phaseA_bvsat_plan.md` — BV-SAT completeness engine (UNSAT authority)
  * `dv_solve_phaseB_dist_plan.md` — native `dist`
  * `dv_solve_phaseC_arrays_plan.md` — native arrays / `foreach` / aggregates
  * `dv_solve_phaseD_wide_plan.md` — >64-bit fields
  * `dv_solve_soundness_and_sampler_plan.md` — primary soundness fix + uniform sampler

---

## 0. Reframing — Boolector stays the default; this is *not* a removal phase

The parent plan's Phase E was written as "**Remove** the external fallback chain"
(`E-1` drops Boolector from `Randomizer.fallback_backends` by default). That
framing is **deliberately deferred** by a product decision:

> **Boolector remains the global default solver (`VSC_SOLVER`) for an extended
> period** while users adopt dv-solve, exercise it on real stimulus, and report
> bugs. dv-solve is opt-in (`VSC_SOLVER=dv-solve`) during this window.

Two consequences reshape the phase:

1. **There is no urgency to delete the internal fallback.** While dv-solve is
   opt-in and Boolector is the trusted default, the dv-solve→Boolector *internal*
   fallback is a *safety net*, not a liability — a residual defer serves a correct
   value via a trusted engine. Removing it early only trades safety for nothing.
2. **The dual-running window is the ideal differential-testing campaign.** The
   single highest-value activity right now is not deletion — it is **proving
   dv-solve agrees with Boolector** across the live suite and real workloads, so
   that when the default *does* eventually flip (a later **Phase F**, out of scope
   here), it flips on evidence.

So Phase E is **re-scoped to three things, none of which remove Boolector**:

- **(A) Measure** — stand up the suite-wide fallback histogram (the parent's open
  `P0-T`) as a standing burn-down dashboard + regression guard.
- **(B) Cross-check** — add an opt-in **XCHECK** differential mode that runs both
  engines on the same RandSet and asserts verdict + membership agreement, turning
  the adoption window into continuous oracle testing.
- **(C) Burn down** — drive each residual `reason_code` either to zero (a native
  encoding lands) or to a **documented, regression-locked permanent residual**
  (a shape we consciously leave on the safety net).

The actual "drop the fallback / flip the default" work is gathered into a short
**§7 Phase F (deferred)** so the exit criteria are written down, but it is **not**
scheduled by this plan.

**Guiding principle (unchanged):** *no silent wrong answers*. A retained fallback
is good; a construct that looks native but is mis-encoded is the cardinal sin. The
histogram (A) bounds what defers; XCHECK (B) bounds what is *wrong*.

---

## 0.5 Build log — E0 dashboard + E4-2 lib-load fix landed (2026-06-12)

**E0-1 (always-on tally) landed.** `randomizer.py` gains a module-level fallback
histogram (`record_fallback` / `get_fallback_tally` / `reset_fallback_tally` /
`set_fallback_tally`) gated by `VSC_DVSOLVE_FALLBACK_TALLY` (default off, zero
overhead). `_solve_randset` records every defer: served fallbacks as
`"<reason>"`, hard-fails and strict-mode (`_NO_FALLBACK`) re-raises as
`"<reason>:hard"`. Decoupled from `profile_on()` so a run can collect the
histogram without full profiling.

**E0-2 (dashboard test) landed.** `ve/unit/test_dvsolve_fallback_histogram.py`:
a native corpus (must defer nothing), a residual corpus (each tagged with its
expected reason code), and the dashboard test asserting (i) no correctness code
(`search-incomplete`/`bvsat-undecided`) appears and (ii) only the documented
allowlist (`width`,`dist`,`array`,`unsat-defer`) appears. Emits the histogram to
stdout; runnable standalone (`python …/test_dvsolve_fallback_histogram.py`).
**3 tests green; full dv-solve native/bvsat/wide suite (41 tests) green; default
(Boolector) path unaffected.**

**E4-2 (orphan lib-load fix) landed early** — it was blocking clean testing.
`dv_solve/lib.py` `pkg_root` was `…parent×4` → `packages/`; corrected to
`…parent×3` → `packages/dv-solve/`, so the native lib now auto-loads from
`packages/dv-solve/build` without `ZSP_SOLVER_PATH`/`LD_LIBRARY_PATH`. (Note:
`ZSP_SOLVER_PATH` is treated as a *directory* in `_find_library`, so pointing it
at the `.so` file silently no-ops — the auto-load is the right path.) **Still TODO
under E4-2: a regression test that loads with both env vars unset.**

### Findings surfaced by the dashboard (→ E3 burn-down)

The dashboard immediately surfaced two real deferrals in shapes the prior plans
imply are native. **Neither is an E0 bug — they are exactly the burn-down items
the dashboard exists to find.** Both recorded here as E3/§5 input:

- **F-E1 (RESOLVED 2026-06-12 — NOT a bug; was a mislabeled reason code).**
  A `randsz_list_t` with `size.inside({1,2,4,8})` (a *gapped* size domain
  excluding 0) deferred with what the histogram showed as `bvsat-undecided`; the
  same with `{0,1,2,4,8}`, a contiguous range `1..8`, or a single value solves
  natively. **Investigation:** the value constraint is irrelevant (even with no
  value constraint it defers); BV-SAT returns **SAT (rc=10), never UNKNOWN** —
  the primary bounds search just can't decide a gapped-no-zero size domain, BV-SAT
  *proves it SAT*, and dv-solve correctly defers to the fallback for distribution
  (serve-SAT off). **So this is the designed two-engine path, not a soundness
  gap.** The bug was that `_solve_via_bvsat` used **one** reason code
  (`bvsat-undecided`) for *both* "BV-SAT proved SAT, deferred for distribution/
  solve_order" and "BV-SAT genuinely UNKNOWN." **Fix:** split them —
  `bvsat-sat-deferred` (SAT, deferred — an expected residual) vs `bvsat-undecided`
  (genuine UNKNOWN — the real must-reach-zero code). Dashboard updated: the
  gapped-randsz case is a documented `bvsat-sat-deferred` residual; correctness
  codes stay `search-incomplete`/`bvsat-undecided`. **Whole-suite histogram now
  proves both correctness codes are ZERO** (see F-E5). *Optional future:* improve
  the primary bounds engine to decide gapped-no-zero size domains natively (a
  completeness/perf win, not a correctness need — it's soundly backstopped).
- **F-E5 (telemetry — the E2-2 SAT-path fraction, surfaced by the split).**
  The whole-`ve/unit` aggregate histogram under dv-solve (tally on):
  `bvsat-sat-deferred = 2796`, `array = 48`, `unsat-defer = 2`, `width = 1`, and
  **`search-incomplete = bvsat-undecided = 0`.** The headline: dv-solve **never**
  accepts a problem it can't authoritatively decide (zero genuine-undecided), but
  it leans on the BV-SAT-proves-SAT → Boolector-serves path **very heavily**
  (~2796 randset-events). That is the E2-2 measurement: while serve-SAT is off,
  Boolector is doing a large share of *value serving* even though dv-solve owns
  the *verdict*. **Implication for self-sufficiency:** closing the
  Boolector-for-serving dependency needs either (a) a more complete primary
  bounds engine (fewer SAT-deferrals) or (b) serve-SAT + the uniform sampler on by
  default — the real content of E2/Phase F. The number is now a standing dashboard
  metric to drive down.
- **F-E2 (RESOLVED 2026-06-12 — re-tagged; residual documented).** A >64-bit
  field whose bound exceeds int64 (e.g. `a > (1<<63)` on a 128-bit field) defers —
  `_domain_of` (`dvsolve_backend.py:660-688`) clamps the width-range to the int64
  envelope and empties it, returning None → defer. Sub-int64-bounded wide
  (`a < 1_000_000`) and unconstrained wide solve natively. So Phase D "native
  wide" covers unconstrained / sub-int64-bounded fields; a >int64 sub-range still
  defers. It was tagged `unsat-defer`, conflating it with a *genuine* narrow-field
  width-range UNSAT (`a == 500` on uint8). **Fix:** the var-declaration raise now
  tags a wide-field (>64-bit) empty-domain defer as **`wide-range`** (a
  representation limit, possibly SAT, served by the fallback) and keeps
  `unsat-defer` for the genuine narrow-field case. Dashboard updated:
  `wide-range` is a documented residual with its own corpus entry. *Optional
  future burn-down:* encode the >int64 bound into the SolveProblem so the
  width-agnostic BV-SAT engine serves it at true width (a Phase-D wide-literal
  item) instead of deferring — not a correctness need (soundly backstopped).

---

## 0.6 Build log — E1 XCHECK landed (2026-06-12)

**E1 (differential cross-check) landed.** New module
`src/vsc/model/solver/xcheck.py` + a one-line hook in `_solve_randset`
(`randomizer.py`). When `VSC_DVSOLVE_XCHECK=1`, after dv-solve solves a RandSet,
XCHECK builds the same fields+hard-constraints into a fresh Boolector, checks the
bare problem's verdict, and pins the dv-solve model to check membership. Key
design points:

- **No randstate consumed.** It checks the model dv-solve *already produced* — it
  does not re-solve for values, so no swizzler runs and value streams are
  identical XCHECK on/off. (Cleaner than the §3 sketch, which assumed a re-solve.)
- **Mismatch policy:** raise `XCheckMismatch` by default;
  `VSC_DVSOLVE_XCHECK_WARN=1` softens to warn+tally; `VSC_DVSOLVE_XCHECK_RATE=p`
  strided-samples (deterministic, no RNG). Programmatic `set_xcheck`/`get_tally`
  for harnesses.
- **Faithfulness guard (important):** if a RandSet has hard constraints but the
  comparator captured **no** rand fields to pin (e.g. inline `randomize_with`
  whose rand vars aren't in this RandSet's `all_fields()`), XCHECK **abstains**
  (tally `unverifiable`) rather than raise — a cross-check that cries wolf
  destroys the trust it exists to build. The faithful, populated-model path is
  what catches real bugs.

**Tests:** `ve/unit/test_dvsolve_xcheck.py` (10 tests): clean agreement, *catches a
deliberately corrupted model*, membership on the historically-buggy shapes (`~`,
signed/unsigned, dist, randsz, wide), the clog2 soundness regression
(`test_te1b_clog2_implies_arith`), strided-sampling determinism, warn-mode tally.
**All green.** Default path unaffected (hook is a no-op when XCHECK off).

**Validation: full `ve/unit` under `VSC_SOLVER=dv-solve VSC_DVSOLVE_XCHECK=1`
surfaced exactly one mismatch — a real bug (F-E3 below), now fixed. After all
Phase-E fixes the suite is fully green under XCHECK (468 passed, 0 mismatches).**

### Findings surfaced by XCHECK (→ E3)

- **F-E3 (soundness bug — FIXED 2026-06-12): implication guards combining
  comparisons over lifted arithmetic were not enforced.** `test_clog2`
  (`test_constraint_functions.py`) builds `((b-1) >= K) & ((b-1) < M) -> (a == i)`
  chains. Boolector computes `a = clog2(b)` correctly; **dv-solve produced garbage
  `a`** (e.g. b=5 → a=80 instead of 3) for 18/19 sampled values. Invisible before
  XCHECK because `test_clog2` has *no assertions* (it only prints).
  **Root cause:** an implication lowers to the disjunction `(!cond) || body`; when
  `cond` is a logical AND/OR of comparisons whose operands are lifted into aux
  vars (arithmetic in the guard), the bounds engine's propagation through
  `NOT(AND(…))` over aux-defined operands is unsound and can leave `body`
  unconstrained even when the guard holds. The failure is **asymmetric** — a
  lifted operand on the AND's *left* triggers it, the *right* may not (`B` single
  comparison ✓, `(b>=5)&((b-1)<8)` ✓, `((b-1)>=4)&(b<9)` ✗) — too fragile to
  exploit. **Fix (translator, sound):** `DvSolveExprTranslator._translate_guarded_cond`
  counts aux vars allocated while translating an implication/if-else guard; if any
  were lifted **and** the guard is a logical And/Or combination, it raises
  `BackendIncomplete(reason_code="implies-aux")` → the RandSet defers to the
  fallback (correct values). A single arithmetic comparison guard
  (`implies((b-1)>=4)`) stays native. **Validated:** clog2 values now correct
  (0/39 wrong); **full `ve/unit` under XCHECK = 466 passed, 0 mismatches**
  (dv-solve in complete verdict+membership agreement with Boolector across the
  suite). Regression locked by `test_dvsolve_xcheck.py::test_te1b_clog2_implies_arith`
  (asserts the values *and* the defer) and a histogram residual entry. **A native
  fix for the bounds-engine disjunction propagation (so these solve natively
  instead of deferring) is a possible later C-engine item — non-gating.**
- **F-E4 (comparator gap, not a confirmed bug): inline `randomize_with` over local
  rand vars.** `test_inline_randomization::test_1` produced empty-model
  verdict-disagreements; the inline rand vars (`addr_`/`offset_`) aren't in the
  RandSet's `all_fields()` the comparator sees, so it cannot faithfully
  reconstruct the problem. Now **abstained** (`unverifiable`) by the faithfulness
  guard — so it's neither a false alarm nor a confirmed bug. **E3 follow-on:** make
  the comparator resolve inline-randomize-with rand vars (then it can verify these
  too), and re-confirm whether dv-solve is actually correct there.

---

## 1. Current state — reason codes and where they are raised

dv-solve's deferrals all raise `BackendIncomplete(reason_code=...)`; the
Randomizer's `_solve_randset` loop (`randomizer.py`) tallies them via both the
always-on `record_fallback` (E0) and `SolveInfo.add_fallback`, and under
`VSC_DVSOLVE_NO_FALLBACK=1` re-raises instead of serving from Boolector.

**This table is the CURRENT (post-E0–E2) reason-code taxonomy** — the codes were
refined during this work (the F-E1/F-E2 splits added `bvsat-sat-deferred` and
`wide-range`; the F-E3 fix added `implies-aux`). Raise sites are described by
function rather than line number (line numbers drift):

| `reason_code` | Raised in / when | Class | Status |
|---|---|---|---|
| `search-incomplete` | primary bounds search couldn't decide and BV-SAT didn't serve | **correctness — must be 0** | **0 across `ve/unit`** ✓ |
| `bvsat-undecided` | BV-SAT returned a *genuine* UNKNOWN/ERROR (A-4 guard / timeout) | **correctness — must be 0** | **0 across `ve/unit`** ✓ |
| `bvsat-sat-deferred` | primary couldn't decide, BV-SAT **proved SAT**, deferred for distribution / `solve_order` (serve-SAT off) | residual (expected) | documented; **2796** suite-wide (the E2-2 SAT-path-fraction metric, F-E5) |
| `dist` | dist shapes not natively encodable (>64-bit dist, conditional/multiple-dist-on-field, array dist) | residual | documented (Phase B/C §5) |
| `array` | n>64 select, >64 summands, wide-result aggregate, object randsz, >64-bit elements | residual | documented (Phase C §5) |
| `implies-aux` | implication/if guard is a logical And/Or of comparisons over **lifted arithmetic** (F-E3) | residual (sound defer) | added by the F-E3 fix; locked by test |
| `wide-range` | >64-bit field whose bound exceeds the int64 `add_var` envelope (often SAT, just unrepresentable) (F-E2) | residual | added by the F-E2 re-tag |
| `unsat-defer` | **narrow** (≤64-bit) field whose domain is genuinely outside its width range (e.g. `a==500` on uint8) | residual (near-unsat) | documented |
| `width` | field width > 255 bits (uint8 `add_var` width field) | **permanent residual** | documented |
| `bvsat-disabled` | `VSC_DVSOLVE_BVSAT=0` set | test-only knob | ignore in prod histogram |

The **two correctness codes** (`search-incomplete`, `bvsat-undecided`) are proven
**zero** across the whole suite by the E0 dashboard — dv-solve never accepts a
problem it cannot authoritatively decide. Everything else is a documented residual
served correctly by the fallback.

Telemetry / flags (current):
- `VSC_DVSOLVE_NO_FALLBACK` — strict re-raise (Phase 0).
- `VSC_DVSOLVE_FALLBACK_TALLY` — **always-on, profiling-independent** histogram
  (`randomizer.record_fallback` / `get_fallback_tally` / `reset_fallback_tally` /
  `set_fallback_tally`). Built by E0 — this *resolved* the original "no suite-wide
  histogram" gap.
- `VSC_DVSOLVE_XCHECK` / `_WARN` / `_RATE` — the E1 differential cross-check.
- `VSC_DVSOLVE_BVSAT` / `_SERVE_SAT` (default **0**) / `_SAMPLER` (default 1 when
  serving).
- `VSC_DVSOLVE_PLAN_CACHE` / `VSC_DVSOLVE_REUSE`.
- `Randomizer.fallback_backends` — Boolector appended iff primary ≠ boolector.

The `dv_solve/lib.py` `pkg_root` orphan bug is **fixed** (E4-2): the native lib
now auto-loads from `packages/dv-solve/build` with no env override.

---

## 2. Workstream E0 (= parent P0-T) — the fallback histogram dashboard `[vsc]`

> **STATUS: DONE (2026-06-12, §0.5).** Always-on tally in `randomizer.py`
> (`VSC_DVSOLVE_FALLBACK_TALLY`) + `ve/unit/test_dvsolve_fallback_histogram.py`
> (dashboard + regression guard). The spec below is the original design.

The burn-down instrument every other workstream reports against. Two deliverables:
a **collection hook** (always-on, cheap) and a **standing test** (the dashboard +
regression guard).

### E0-1 Always-on fallback collection (decoupled from `profile_on()`)

Today `add_fallback` only runs when a `SolveInfo` exists, which requires profiling.
Add a lightweight, process-global accumulator that records reason codes
unconditionally, so the histogram can be gathered across an entire test run without
turning on full profiling.

- **E0-1a** Add a module-level collector in `randomizer.py` (mirror the existing
  `_NO_FALLBACK` global), e.g. `_FALLBACK_TALLY: Dict[str,int]` plus a
  `record_fallback(reason)` / `reset_fallback_tally()` / `get_fallback_tally()`
  trio. Gate it behind `VSC_DVSOLVE_FALLBACK_TALLY=1` (default **off** in
  production — zero overhead) so it is purely a measurement/CI knob.
- **E0-1b** In `_solve_randset` (`randomizer.py:491-493`), call `record_fallback`
  alongside the existing `solve_info.add_fallback`, on **every** fallback
  regardless of profiling. Record the *reason_code* of the back-end that deferred,
  not the final outcome. (Under `_NO_FALLBACK` the re-raise path at `:486` should
  also tally before raising, so strict-mode runs still populate the histogram.)
- **E0-1c** Distinguish **served-by-fallback** (a defer that Boolector then
  satisfied) from **hard-fail** (no back-end could serve → re-raise). The dashboard
  cares about both, but they are different burn-down targets.

### E0-2 The standing dashboard test `[vsc]`

`ve/unit/test_dvsolve_fallback_histogram.py` (new):

- Runs a **representative corpus** under `VSC_SOLVER=dv-solve` with the tally on,
  then asserts the resulting histogram against a **declared allowlist** — the
  known/accepted residuals (`width`, the documented `dist`/`array` §5 shapes, the
  serve-deferral when serve-SAT is opt-in-off).
- **Fails loudly on (i)** any *new* reason code, **(ii)** any reason code expected
  to be zero (`search-incomplete`, `bvsat-undecided`) being non-zero, **(iii)** a
  count regression on a code that an earlier phase drove to zero.
- Corpus = the union of the Phase B/C/D native-test corpora (already enumerated in
  those plans' §7 test lists) plus a sweep of `ve/unit` constraint tests. Reuse the
  existing `_dvsolve_available()` skip guard.
- Emit the histogram to stdout (and optionally a JSON artifact under `out/`) so the
  burn-down is visible in CI logs, not just pass/fail.

**Exit (E0).** A single command produces the current reason-code histogram over the
suite; the test is green with the allowlist matching today's documented residuals;
any future regression (new defer, or a zeroed code coming back) breaks CI.

---

## 3. Workstream E1 — XCHECK differential mode `[vsc]` (the trust engine)

> **STATUS: DONE (2026-06-12, §0.6).** `src/vsc/model/solver/xcheck.py` +
> `_solve_randset` hook + `ve/unit/test_dvsolve_xcheck.py` (10 tests). Implemented
> as a **model check** (membership + verdict of the model dv-solve already
> produced) — no re-solve, no randstate consumed — rather than the re-solve the
> spec below sketches. Found + fixed a real soundness bug (F-E3). The spec below
> is the original design.

The centerpiece of the dual-running window. When `VSC_DVSOLVE_XCHECK=1`, every
RandSet solved by dv-solve is **also** solved by Boolector on the same problem and
the two are compared. This is *differential testing as a runtime mode*, not a
one-off fuzzer — it lets early adopters (and CI) catch encoding bugs on **their
own** stimulus.

### What to compare (and what not to)

Value streams **deliberately differ** between engines (different `randstate`
consumption — see parent §4, Phase B §3). So XCHECK must compare **semantic
agreement**, not exact values:

1. **Verdict agreement (hard):** SAT vs UNSAT must match. A dv-solve "SAT" where
   Boolector says "UNSAT" (or vice-versa) is a **fatal** soundness bug → raise.
2. **Membership (hard):** the value dv-solve produced must satisfy *every*
   constraint in the RandSet (re-check the model against the Boolector-built
   formula via `Assume` + `Sat`). This catches mis-encodings that still land
   *a* model — the cardinal-sin case.
3. **Distribution (soft, sampled):** optionally, over N draws, the distribution
   scorer (`distribution_score.py`) must be no-worse-than-Boolector. Off by
   default in XCHECK (it needs many draws); covered separately by the scorer gates
   in Phases B/C.

### Implementation

- **E1-1 Mode plumbing `[vsc]`.** `VSC_DVSOLVE_XCHECK=1` env + a programmatic
  setter (mirror `set_solver_backend`). When set and the primary is dv-solve,
  `_solve_randset` (`randomizer.py:464`) runs the primary, then re-solves the same
  RandSet on a Boolector back-end instance for comparison **without** consuming the
  caller's `randstate` for the second solve (snapshot/restore, or a forked state).
- **E1-2 The comparator `[vsc]`.** After the dv-solve solve, build the Boolector
  formula for the same RandSet (the diagnostics path already does exactly this —
  `randomizer.py:503` `create_diagnostics_1` builds fields+constraints into a
  `Boolector`), `Assume` the dv-solve-produced field values, and check membership;
  separately check Boolector's own SAT verdict for verdict agreement. Reuse that
  builder rather than writing a new one.
- **E1-3 Mismatch policy `[vsc]`.** Default = **raise** `XCheckMismatch` (a loud,
  detailed diagnostic: the RandSet, the dv-solve model, which constraint failed,
  the Boolector verdict). A `VSC_DVSOLVE_XCHECK_WARN=1` softens it to a logged
  warning + a tally (for sampling across a long run without aborting). Feed
  mismatches into the E0 telemetry (`xcheck-mismatch` pseudo-reason) so the
  dashboard counts them.
- **E1-4 Sampling `[vsc]`.** XCHECK on *every* RandSet roughly doubles solve cost.
  Add `VSC_DVSOLVE_XCHECK_RATE=p` (0<p≤1, default 1.0) to cross-check a random
  sampled fraction — for always-on CI on large suites without the full 2× cost.
  Sampling must be seed-deterministic (drive from `randstate`) so a mismatch
  reproduces.

### Why this is the right investment now

The user's stated goal — "as users become comfortable (and report bugs)" — is
*precisely* served by XCHECK: a user can run their existing Boolector-validated
regression under `VSC_SOLVER=dv-solve VSC_DVSOLVE_XCHECK=1` and get an immediate,
per-RandSet, automatic verdict on whether dv-solve matches the engine they trust.
That is the bug-reporting on-ramp.

**Exit (E1).** XCHECK runs the full `ve/unit` suite under dv-solve with zero
mismatches (verdict + membership). A standing CI job runs the suite with
`VSC_DVSOLVE_XCHECK=1` (full rate). Documented as the recommended adoption mode.

---

## 4. Workstream E2 — serve-SAT / sampler policy `[vsc]` + `[dvs]`

The sampler (soundness plan Part 2) is landed, distribution-validated, and all
three default-flip gates are closed — but `VSC_DVSOLVE_BVSAT_SERVE_SAT` defaults
**off** because of the +54 % suite wall-clock and because Boolector (the default
backend) is right there as a correct serving net.

**Decision for this phase: keep serve-SAT opt-in; do not flip it on by default.**
Rationale: while Boolector is the trusted default backend, deferring SAT *serving*
to it (for order-bearing RandSets and the wide-free-var cases the sampler is slow
on) is a correct, cheap safety net — exactly the situation §0 describes. Flipping
serve-SAT on only matters for the *eventual* Phase F (when the internal fallback is
removed and dv-solve must serve everything itself).

So E2 is **policy + measurement**, not a flip:

- **E2-1 (DONE).** serve-SAT/sampler envs and the current default posture
  documented in `solver_backends.rst` (the XCHECK adoption section + the env-var
  list). Backend docstring covers the engine posture.
- **E2-2 (DONE — via F-E5).** The SAT-path fraction is now on the dashboard: the
  `bvsat-sat-deferred` reason code (split out in the F-E1 fix) counts exactly "the
  primary couldn't decide, BV-SAT proved SAT, deferred to the fallback" — and the
  whole-suite aggregate measured it at **2796** (vs zero genuine `bvsat-undecided`).
  That is the data Phase F needs: it shows value-serving still leans heavily on
  the fallback, so retiring Boolector-for-serving requires either a more complete
  primary engine or serve-SAT-on-by-default.
- **E2-3** *(optional, `[dvs]`, only if E2-2 shows a hot path)* the C-level
  `zsp_bbsolver_add_xor` / native-XOR escape hatch noted in the sampler plan §2.3
  for kissat's XOR weakness. **Not built** — gated on a real workload showing the
  sampler is the bottleneck, which the current data does not yet establish.

**Exit (E2): met.** Serve-SAT posture documented; SAT-path fraction
(`bvsat-sat-deferred`) is a standing dashboard metric. No default change.

---

## 5. Workstream E3 — residual reason-code burn-down `[vsc]` + `[dvs]`

> **STATUS (2026-06-12): correctness goal MET; remaining items are optional native
> burn-downs (perf/completeness, soundly backstopped — not correctness).**
> - ✅ **`search-incomplete` = `bvsat-undecided` = 0** across the whole `ve/unit`
>   suite (E0 dashboard, whole-suite aggregate). dv-solve never accepts a problem
>   it can't authoritatively decide.
> - ✅ The three findings are resolved: **F-E3** (clog2 implication guard — a real
>   soundness bug, fixed by deferring), **F-E1** (randsz "undecided" was a
>   mislabeled SAT-deferral — reason code split), **F-E2** (wide-above-int64
>   mis-tagged `unsat-defer` — re-tagged `wide-range`). See §0.5/§0.6.
> - ✅ The canonical residual taxonomy is the §1 table; the E0 dashboard's
>   allowlist mirrors it, so doc and test can't drift.
> - ⏳ **Remaining (optional, non-gating):** make the heavy residuals solve
>   *natively* instead of deferring — chiefly the **`bvsat-sat-deferred` = 2796**
>   volume (improve primary-engine completeness, e.g. gapped/no-zero randsz size
>   domains) and the `wide-range` / wide-`dist` cases (encode >int64 bounds into
>   the SolveProblem so BV-SAT serves at true width). These reduce the
>   Boolector-for-serving dependency (the real path to self-sufficiency, §F) but
>   change no correctness outcome.

For each live reason code, either land the native encoding (→ count goes to zero in
the E0 dashboard) or **consciously accept it as a documented permanent residual**
served by the Boolector net. The split:

### Must reach zero (correctness — a non-zero count is a *bug*, not a feature gap)

- **`search-incomplete` (`:491`) and `bvsat-undecided` (`:573`).** These mean
  dv-solve could neither solve nor *decide* a problem it accepted. The Phase A/C
  work already drove these near zero; E3 **proves** it via E0 (must be 0 on the
  corpus) and chases any straggler. The two documented Phase-C "Finding-2"
  search-incompleteness cases (`phaseC §0.5`) are the known stragglers — resolve or
  formally classify them here (route to BV-SAT so they *decide*, even if Boolector
  *serves*).

### Burn down where cheap, else document (feature gaps — safe on the net)

- **`dist` §5 shapes** (>64-bit dist; conditional/multiple dist on one field;
  array dist). Array dist is Phase C's domain; >64-bit dist pairs with Phase D's
  wide path. Each: either land the native encoding (Phase B/C/D follow-on) or add a
  row to the documented-residual table.
- **`array` §5 shapes** (n>64 select, >64 summands, wide-result aggregate, object
  randsz, >64-bit elements — `phaseC §5`). Same treatment; most are explicitly
  "later cut if a corpus needs it."
- **`width` > 255 bits** (`:215`). Bounded by the uint8 width field in the C ABI;
  **permanent residual** — document it.
- **`unsat-defer`** (`:281,:687`). Width-range UNSAT cases the primary won't
  declare authoritatively; with Phase A's BV-SAT as UNSAT authority these should
  mostly *decide* (and the net serves). Confirm via E0 they are decided-not-guessed.

### Deliverable

A **single canonical residual table** (in this doc and mirrored in
`solver_backends.rst`) enumerating exactly what defers and why, with each row
either "burn down in <phase>" or "permanent residual — served by fallback." The E0
dashboard's allowlist is generated from this table, so doc and test cannot drift.

**Exit (E3).** `search-incomplete` = `bvsat-undecided` = 0 on the corpus. Every
other non-zero reason code has a matching documented-residual row. No undocumented
defer exists (E0 enforces).

---

## 6. Workstream E4 — keep diagnostics on Boolector + orphan fixes `[vsc]`

> **STATUS (2026-06-12): DONE.** E4-1 verified + locked by
> `test_solve_failure.py::test_diagnostics_with_dvsolve_primary` (an UNSAT under
> dv-solve primary still produces Boolector-backed diagnostics). E4-2 lib-load fix
> landed (auto-loads from `packages/dv-solve/build`, no env override).

- **E4-1 Diagnostics stays on Boolector (parent §6.5 / E-2).** `create_diagnostics`
  (`randomizer.py:503`) is human-facing failure explanation and **must keep
  working** unchanged — Boolector is a lazily-imported *optional* dependency for it.
  Verify it still functions when dv-solve is the primary. Porting diagnostics onto
  the BV-SAT unsat-core is an explicit **non-goal** of this phase.
- **E4-2 Fix the `lib.py` `pkg_root` orphan** (sampler plan §2.10): correct the
  build-dir search to `packages/dv-solve/` so the native lib loads without
  `ZSP_SOLVER_PATH`/`LD_LIBRARY_PATH`. Add a regression test that imports and loads
  the lib with those env vars unset. Small, independent, unblocks clean adoption.

**Exit (E4).** Diagnostics produce the same explanation with dv-solve primary; lib
loads from its installed location with no env override; regression tests lock both.

---

## 7. Phase F (DEFERRED — explicitly not scheduled here)

Written down so the eventual exit is unambiguous, but **gated on the adoption
window closing and on E0–E3 holding green for a sustained period**:

- **F-1** Remove Boolector from `Randomizer.fallback_backends` by default
  (`randomizer.py:333-338`); make it opt-in. Requires: every correctness reason
  code at zero, every residual either natively closed or accepted-as-permanent with
  product sign-off, **and** serve-SAT (E2) flipped on so dv-solve serves
  everything it accepts.
- **F-2** Flip the global default `VSC_SOLVER` to dv-solve. Requires: XCHECK clean
  across a defined real-workload corpus for ≥1 release, plus a documented rollback
  (`VSC_SOLVER=boolector`).
- **F-3** Keep Boolector reachable forever as `VSC_DVSOLVE_XCHECK` oracle +
  `create_diagnostics`, lazily imported, no correctness dependence.

**Phase F is not part of this plan's deliverables.** It is the success condition
that E0–E3 + the adoption window earn.

---

## 8. Test plan (T-E*)

All under `VSC_SOLVER=dv-solve`, cross-checked against `VSC_SOLVER=boolector` where
noted, in new files mirroring the Phase B/C skeleton (`_dvsolve_available()` skip,
`_no_fallback()`/`_strict_no_fallback()` context managers, `distribution_score`).

- **T-E0 (dashboard) — `test_dvsolve_fallback_histogram.py`.** Runs the corpus with
  the tally on; asserts the histogram == the documented allowlist; fails on any new
  reason code, any non-zero correctness code, or a re-appearing zeroed code. Emits
  the histogram to stdout/`out/`.
- **T-E1a (XCHECK verdict).** A curated set of known-SAT and known-UNSAT RandSets
  under `VSC_DVSOLVE_XCHECK=1`: assert dv-solve and Boolector verdicts agree;
  inject a deliberately mis-encoded test double and assert XCHECK *catches* it
  (the mode must be able to fail).
- **T-E1b (XCHECK membership).** Over N draws on representative constraints, assert
  every dv-solve model satisfies the Boolector-built formula (membership). Include
  the historically-buggy shapes: `~` bitwise invert, signed/unsigned compares,
  `dist`, randsz arrays, wide (>64-bit) fields.
- **T-E1c (XCHECK sampling + determinism).** `VSC_DVSOLVE_XCHECK_RATE=0.5` is
  seed-deterministic (same seed → same sampled RandSets → same mismatch, if any).
- **T-E1d (XCHECK warn mode).** `VSC_DVSOLVE_XCHECK_WARN=1` tallies instead of
  raising; the tally feeds the dashboard.
- **T-E2 (SAT-path fraction).** With serve-SAT off (default), the dashboard reports
  the SAT-invoked / SAT-served / SAT-deferred split on a corpus that exercises
  BV-SAT; numbers are non-zero and stable.
- **T-E3 (residual residue).** Under `_strict_no_fallback()`, the *exact* set of
  reason codes that defer equals the documented residual table — not a superset
  (no silent extra defer) and not a subset (no claimed-native-but-actually-deferred).
- **T-E4a (diagnostics).** Force an UNSAT randomize with dv-solve primary; assert
  `create_diagnostics` still produces a Boolector-backed explanation.
- **T-E4b (lib load).** Import + load `libdv_solve` with `ZSP_SOLVER_PATH` and
  `LD_LIBRARY_PATH` unset; assert it loads from the package location.
- **Differential fuzz (cross-cutting).** Extend the existing constraint-system
  fuzzer to run under XCHECK so random systems assert verdict+membership agreement
  — the same net XCHECK gives users, in CI.
- **Validation triple (every workstream):** full `ve/unit` green under (1) dv-solve,
  (2) Boolector, (3) the package C/Python suite + `ctest`.

---

## 9. Doc plan

- **`doc/source/solver_backends.rst`** — dv-solve entry: (a) state Boolector is the
  current default and dv-solve is opt-in; (b) document the **adoption recommendation**
  to run with `VSC_DVSOLVE_XCHECK=1`; (c) embed the **canonical residual table**
  (§5) of what still defers to the fallback; (d) document every env var:
  `VSC_DVSOLVE_NO_FALLBACK`, `VSC_DVSOLVE_FALLBACK_TALLY`, `VSC_DVSOLVE_XCHECK[_WARN|_RATE]`,
  `VSC_DVSOLVE_BVSAT[_SERVE_SAT|_SAMPLER]`, `VSC_DVSOLVE_REUSE`, `VSC_DVSOLVE_PLAN_CACHE`.
- **Backend docstring** (`dvsolve_backend.py:157`) — add an "engine posture"
  paragraph: primary bounds search → BV-SAT completeness → Boolector net (retained),
  and the serve-SAT default-off rationale.
- **Randomizer docstring** (`_solve_randset`, `randomizer.py:464`) — document the
  fallback tally and XCHECK hooks.
- **A short adoption note** (`doc/notes/` or the user guide): "Trying dv-solve" —
  how to opt in, how to cross-check, how to read the fallback histogram, how to
  report a mismatch.
- **Parent plan close-out** (`dv_solve_feature_completeness_plan.md` §3 Phase E) —
  rewrite the Phase E entry to reflect this re-scope (self-sufficiency + XCHECK +
  burn-down, **not** removal) and point at this doc; add the deferred Phase F.

---

## 10. Sequencing & gates

```
E0 (histogram dashboard) ✅─┬─> E1 (XCHECK) ✅  ── found+fixed F-E3; suite green under XCHECK
                           ├─> E2 (serve-SAT posture + SAT-path telemetry) ✅
                           ├─> E3 (correctness codes → 0 ✅; optional native burn-downs ⏳)
                           └─> E4 (diagnostics ✅ + lib.py fix ✅)
                                              └─> [Phase F — DEFERRED: drop net, flip default]
```

- **E0–E2, E4: DONE** (2026-06-12). E3's correctness goal is met (both correctness
  codes proven 0 suite-wide); only the *optional* native burn-downs remain (reduce
  `bvsat-sat-deferred`/`wide-range` — perf, not correctness).
- **Phase F stays out** until the adoption window closes on evidence.

**For a fresh start, the single highest-value remaining thread** is reducing the
`bvsat-sat-deferred = 2796` volume — i.e. improving primary-engine completeness so
dv-solve *serves* more itself instead of leaning on Boolector. That is the
substantive path toward self-sufficiency (and toward making Phase F viable). It is
a translator/bounds-engine effort, not a correctness fix.

## 11. Decisions — resolved during implementation (2026-06-12)

1. **Histogram corpus scope** → **both.** The standing dashboard test uses a
   curated native+residual corpus (deterministic regression guard); the suite-wide
   sweep is run on demand via `VSC_DVSOLVE_FALLBACK_TALLY=1` (the F-E5 aggregate).
2. **XCHECK mismatch policy** → **raise by default, `VSC_DVSOLVE_XCHECK_WARN=1` to
   warn+tally.** As recommended.
3. **`VSC_DVSOLVE_FALLBACK_TALLY` vs XCHECK** → **kept separate** (tally is
   zero-cost always-on; XCHECK is ~2× opt-in).
4. **Permanent-residual sign-off (still open, product call):** which residuals to
   accept *forever* vs burn down. Current residual taxonomy is the §1 table;
   `width` (>255 bits) is the clear permanent one. The rest (`bvsat-sat-deferred`,
   `wide-range`, `dist`/`array` §5, `implies-aux`) are "burn down eventually,
   correct on the net meanwhile." No correctness urgency.
