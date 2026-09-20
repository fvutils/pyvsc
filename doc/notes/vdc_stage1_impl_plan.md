# Stage 1 — non-breaking overhead removal: implementation & validation plan

Status: **active / tracking doc** · opened 2026-09-20 · last updated 2026-09-20

**Progress:** S1.0 ✅ · S1.1 ✅ · S1.2 ✅ · S1.3 ✅ · S1.4, S1.5, S1.7 open.
`arr128` warm: 4 455 → **10 739** solves/sec so far (target 13 000).
Live numbers: `benchmarks/RESULTS_stage1.md`.
Parent: `doc/notes/vdc_value_representation_plan.md` (this is that document's
"Stage 0" — renamed Stage 1 here because it is the first stage we are building).
Evidence: `doc/notes/dv_solve_boundary_overhead_findings.md` §7, §7a, §7b.

**Goal.** Remove the measured, *modeler-invisible* overhead from `randomize()`
on the dv-solve + vdc path, and then re-measure so the representation question
(§3 gate of the parent plan) can be decided on numbers rather than argument.

**Non-goals.** No change to any modeler-visible behaviour. No change to
semantics. No representation change. No new public API except one opt-in batch
entry point (S1.6), which is additive. Classic `@vsc.randobj` and the boolector
path must come through byte-identical in behaviour — several of these changes
land in code shared by both, so "classic is unaffected" is a claim to be
*tested*, not assumed.

---

## 0. Baseline and target

Measured `arr128`, warm, same box (findings §7b):

| step | µs/solve | solves/sec | status |
|---|---:|---:|---|
| pre-investigation baseline | 231 | 4 320 | — |
| `ValueScalar.__int__` fix | 160 | **6 224** | ✅ S1.0 landed (`b4f27b5`), re-measured |
| + bulk readback | **122.5** | **8 153** | ✅ S1.2 landed, re-measured |
| + skip copy-in for enabled rand fields | **96.7** | **10 739** | ✅ S1.3 landed, re-measured |
| + pay-per-use housekeeping walks | ~74 | ~13 500 | S1.4 |
| *constrainedrandom 1.3.0, same box* | *26.5* | *37 763* | reference |
| *structural ceiling (findings §5)* | *15.5* | *64 556* | reference |

Measured phase split at the S1.0 baseline (`arr128` warm, 167.3 µs/solve): native
solve **19.8%**, readback 28.8%, `apply_node` copy-in 17.7%, the four
housekeeping walks 18.2%, writeback 3.7%. On `basic` (14.0 µs/solve) the walks
are 28.3% and the `rollback` walk alone costs more than the solve. Full tables
in `benchmarks/RESULTS_stage1.md`.

Stage 1 target: **≥ 13 000 solves/sec on `arr128`** (≈3.1× over the current
committed tree, ≈2.2× over the already-applied `__int__` fix) with no behavioural
delta on any suite. The remaining gap to cr is the T0 tier (Stage 2), which is
out of Stage 1's scope.

Secondary targets (must not regress): `basic`, `arr32`, `randc`, the dist
workloads, and every read-side path.

---

## 1. Workstreams

Ordered by *certainty*, not by size. Each lands independently, behind its own
env kill-switch, with its own tests, and is separately revertible.

### S1.0 — Validate and land the `ValueScalar.__int__` fix  ✅ **DONE** (`b4f27b5`)

`src/vsc/model/value_scalar.py` is modified in the working tree and unvalidated
beyond `ve/unit_dc`. Nothing else in this plan should be measured on top of an
unvalidated base.

- Change: `__int__` returns `self.v` (a plain `int`) instead of `ValueInt` (an
  `int` subclass, which put every `int()` on CPython's deprecated-conversion
  path — 411.7 ns vs 50.1 ns, ~256 calls/solve). `toInt()` remains the
  `ValueInt`-returning accessor.
- Risk: any caller that relies on `int(value_scalar)` returning something with
  `__getitem__` (bit-slicing). `src/vsc/types.py:593` is the only `toInt()` user
  found; audit again for `int(` on a `ValueScalar` followed by a subscript.

**Validation (all four must pass before anything else lands):**
- [x] `ve/unit` on dv-solve — 517 passed, 1 failed
- [x] `ve/unit` on boolector — 517 passed, 1 failed
- [x] `ve/unit_dc` on dv-solve — 313 passed
- [x] `ve/unit_dc` on boolector — 283 passed, 30 skipped
- [x] grep audit: no `int(...)` result of a `ValueScalar` is subscripted anywhere
- [x] commit as its own change, with the measurement in the message

The single `ve/unit` failure —
`test_dvsolve_array_native::test_tc2_fixed_product` ("dv-solve fell back to
Boolector for a RandSet") — reproduces on a **fully clean tree** with every
working-tree modification stashed, on both back-ends. Pre-existing and
unrelated; out of Stage 1's scope, but it should be filed.

Measured on `bench_stage1.py` (warm, dv-solve): `arr128` 4 455 → 6 279 (1.41×),
`arr32` 15 885 → 21 881 (1.38×), `basic` 78 255 → 85 878 (1.10×) — consistent
with the findings doc's 1.46× / 1.37×.

This fix is front-end- and back-end-agnostic, so it is also the one most likely
to surface a latent assumption somewhere in classic. Landed alone.

---

### S1.1 — Measurement harness  ✅ **DONE**

Nothing later is trustworthy without per-phase attribution that we can re-run on
demand. The parent plan's R2 needs this harness anyway.

- [x] `benchmarks/_stage1_workloads.py` — nine workloads: `basic`, `nested`,
      `soft`, `randc`, `hooks`, `knob`, `packet16`, `arr32`, `arr128`. One per
      *shape Stage 1 can affect*, plus the feature shapes whose walks S1.4 wants
      to make conditional, so a step that speeds up `arr128` while regressing
      `soft` is visible rather than buried in a geo-mean.
- [x] `benchmarks/bench_stage1.py` — throughput ladder (one column per switch),
      `--attrib` phase attribution, `--all`, `--cold`, `--scale`, `--workload`,
      and an explicit pass/fail against the 13 000 solves/sec target.
- [x] `src/vsc/model/phase_timers.py` — real timers (**not** cProfile) at
      `apply_node`, `set_used_rand`, `clear_soft_pri`, `pre_randomize`,
      `randinfo_build`, `solve`, `readback`, `rollback`, `post_randomize`,
      `writeback`, plus an `(unattributed)` remainder. Enabled by
      `VSC_PHASE_TIMERS=1`, read once at import.
      **Not zero-cost when off** — two stub calls (~100 ns) per site, which is a
      few percent of the target budget. Handled by taking headline numbers in a
      *separate process* with the variable unset; `--all` does this
      automatically. This is the honest fix; pretending the stubs are free is not.
- [x] `src/vsc/model/opt_flags.py` — `VSC_S1_BULK_READBACK`, `VSC_S1_SKIP_COPYIN`,
      `VSC_S1_LAZY_WALKS`, defaulting to on, settable in-process so the ladder
      times the same live objects under each configuration.
- [x] `benchmarks/RESULTS_stage1.md` — dated pre-optimization baseline.

Two things the first run of the harness changed about the harness itself:

1. **Sequential config sweeps are biased.** The first ladder reported a spurious
   1.28× on `basic` while every switch was still a no-op, purely because later
   columns ran on a hotter cache. Fixed by sweeping the configs `--reps` times
   interleaved and keeping the best per config; the baseline ladder is now flat
   at 1.00× geo-mean, which is the correct answer and the harness's own
   acceptance test.
2. **The `hooks` workload was measuring the wrong thing** — see S1.7.

**Validation:** ✅ reproduces the findings-doc §7b post-`__int__` numbers within
~5% (`arr128` 6 224 vs 6 131; `arr32` 21 624 vs 19 870), and the all-switches-off
ladder is flat.

---

### S1.2 — Bulk readback  ✅ **DONE**

**Result: `arr128` 6 374 → 8 153 solves/sec (1.28×), 160 → 122.5 µs/solve.**
`arr32` 1.21×, `packet16` 1.13×; scalar workloads flat, as expected (a 1–2
field readback has nothing to batch). Slightly ahead of the ~7 600/s estimate.

Landed as `_BulkReadback` in `dvsolve_backend.py` (pre-built `c_uint32*n` id
array + `c_int64*n` output buffer + a precomputed mask per entry, all cached for
the life of the compiled ctx) plus `SolveCtx.get_values` in dv-solve
(`197d920`). Built **lazily on first reuse**, so a plan that is never reused
does not pay to construct the buffers.

Two things worth recording:

- The mask precomputation specialises the uniform case. An array of one unsigned
  type — the shape this whole step exists for — collapses to a single mask, and
  the hot loop then drops a `zip` leg. Mixed widths fall back to a per-entry
  mask list. Semantics are identical to `_as_field_value` in all three cases.
- `get_value` also lost its per-call `ctypes.c_uint32(var_id)` (~18% of each
  remaining scalar FFI call). The same pattern recurs throughout `problem.py`
  and was left alone there — not on a hot path.

**Validation:** ✅ all of the below.
- [x] `packages/dv-solve` `tests/unit` — 759 passed
- [x] new `ve/unit/test_dvsolve_bulk_readback.py` — bulk vs scalar equivalence
      across widths 1/8/32/63/64 × both signednesses, the u64-with-bit-63-set
      case the masking exists for, mixed widths/signs, single element, the
      `_BulkReadback` mask precomputation itself, and a switch-on vs switch-off
      stimulus-identity test over 12 randomizes (so plan reuse is covered)
- [x] `ve/unit` + `ve/unit_dc` on dv-solve **and** boolector — no new failures
- [x] XCHECK soak — no new failures
- [x] ASAN full `ve/unit` slice — clean, 528 passed

Two pre-existing failures confirmed unrelated (both reproduce with this step's
changes removed): `test_dvsolve_array_native::test_tc2_fixed_product` and, under
XCHECK, `test_randomization::test_simple`.

<details><summary>original plan text</summary>

The per-element FFI readback is **33 µs = 48.1% of the post-fix budget** on
`arr128`, and a bulk C entry point already exists, is wired, and is unit-tested —
it has simply never been called.

Code sites:
- `packages/dv-solve/src/c/zsp_search.c:1040` — `solver_get_values(ctx, n, var_ids, out)`, exists.
- `packages/dv-solve/src/dv_solve/lib.py:216` — argtypes declared, exists.
- `packages/dv-solve/src/dv_solve/ctx.py` — **no Python `get_values` method**; add one.
- `src/vsc/model/solver/dvsolve_backend.py:754` — `solve_merged` readback loop
  (`for f, vid, w, s in readback: f.set_val(...ctx.get_value(vid)...)`).
- `src/vsc/model/solver/dvsolve_backend.py:850` — the per-RandSet
  `_solve_and_readback` loop; same treatment.

Implementation:
- [ ] `SolveCtx.get_values(ids_arr, out_arr, n)` in `ctx.py`, taking **caller-owned,
      pre-built** `ctypes` arrays — the point is to allocate nothing per solve.
- [ ] Cache the `(c_uint32 * n)` id array and the `(c_int64 * n)` output buffer on
      the object that owns `readback` — `_CompiledPlan` (`dvsolve_backend.py:226`,
      extend `__slots__`) and the `plan.merged` tuple. The var-id list is fixed for
      the life of a compiled ctx, so it is built exactly once.
- [ ] Materialise with `memoryview(out).cast('B').cast('q').tolist()` — measured at
      the Python-int allocation floor (0.267 µs vs 0.281 µs); `list(buf)` is 14×
      worse. The `.cast('B').cast('q')` dance is required: a direct `.cast('q')`
      on a `c_int64` array raises `NotImplementedError: memoryview: unsupported
      format <q`.
- [ ] Apply width/sign reinterpretation (`_as_field_value`,
      `dvsolve_backend.py:873`) over the materialised list. Precompute the
      `(width, signed)` masks once per readback list rather than per element —
      most fields need no mask at all, so precompute the *set of indices that do*.
- [ ] Drop the per-call `ctypes.c_uint32(var_id)` allocation in
      `ctx.get_value` (`ctx.py:369`) — `argtypes` already declares `c_uint32`, so
      a plain Python int converts automatically. That is ~18% of every remaining
      scalar FFI call, and the same pattern recurs throughout `problem.py`; fix it
      where it is on a hot path, note the rest.

Expected: 33 µs → ~4.4 µs on `arr128` (7.6×), ~12.5% of total.

**Validation:**
- [ ] `packages/dv-solve` `tests/unit` (incl. `test_reset.py`, which already
      covers `solver_get_values`)
- [ ] new: bulk and scalar readback return identical values for the same solved
      ctx, across widths 1/8/32/63/64 and both signednesses — this is where a
      sign-extension bug would hide
- [ ] new: `>64`-bit fields still take the wide path and are **excluded** from the
      bulk buffer (an `int64` out-array cannot represent them)
- [ ] new: a readback list of length 0 and of length 1 (boundary)
- [ ] `ve/unit` + `ve/unit_dc` on dv-solve; XCHECK run against boolector
- [ ] ASAN run (`ve/run_asan.sh`) — this step introduces new pointer-passing, and
      the project has already been bitten once by an unwired-ctypes pointer
      truncation that only crashed under high-address heaps

</details>

---

### S1.3 — Skip copy-in for enabled rand fields  ✅ **DONE**

**Result: `arr128` 8 129 → 10 739 solves/sec (1.32×), 122.5 → 96.7 µs/solve.**
Cumulative from the S1.0 baseline: **1.72×**. `arr32` 1.29× (26 577 → 34 184),
`packet16` 1.22×, and — unlike S1.2 — the scalar workloads gain too
(`basic` 1.13×, `nested` 1.11×, `hooks` 1.11×), because every type pays copy-in.
Cold (create-many) tracks warm: `arr128` 1.30×, geo-mean 1.19×. Well ahead of
the ~8 800/s estimate.

`apply_node` went from **29.58 → 0.30 µs/solve** on `arr128` (99×), i.e. it is
now off the profile entirely.

Implemented as a per-node `skip_copyin` frozenset computed once per type in
`build_solve_node` and consulted by a single `continue` at the top of
`_apply_node`'s field loop — rather than the planned second `_apply_fast`
function. One code path is easier to keep correct than two, and the set is
already precomputed, which is where the cost was.

**What qualifies for the skip** (`_skippable_copyin`) is narrower than the plan
assumed, in three ways found while implementing:

1. **`parent_rand` chain.** `FieldCompositeModel.set_used_rand` only propagates
   rand-ness through parents that are themselves declared rand, so a rand field
   under a *non*-rand composite is never used-rand and its value must be copied
   in. The flag is threaded down `build_solve_node`.
2. **randc is excluded.** `cyclic.py`'s fast path sets `fm.rand_mode = False`
   and a value directly, and restores `rand_mode` **only on its bail path** — so
   the next `_apply_node` is what puts it back to True. Skipping would strand
   the field at `rand_mode=False`; the exclusion fallback would then treat it as
   a constant at its stale value. Worth noting that a behavioural test does
   *not* catch this (cyclic re-sets `rand_mode=False` before each solve anyway),
   which is why the test for it is a structural assertion on the skip set.
3. **Random-size arrays are excluded**, as the plan's conservative option.
   Elements past the solved size are variables but are not written back, so
   their model values are not provably solver-owned. Verified by mutation that
   including them does not break the current tests — kept out anyway, since
   "the tests don't catch it" is not the same as "it is sound", and rand-size
   arrays are not the shape this step exists for.

**`rand_mode` restoration.** A per-node `rm_dirty` flag: once an apply has
written per-instance `rand_mode` onto a node's models, the *next* apply takes
the full path even with no override present, so the models get `rand_mode=True`
restored rather than inheriting a previous instance's `False`. Without this, a
`set_rand_mode(name, False)` on one instance would silently pin that field for
every other instance of the type, because the solve model is shared per type.
Covered by `test_c1b_rand_mode_restored_after_reenable` and
`test_c1c_rand_mode_disabled_on_a_second_instance`.

**Validation:** ✅ `ve/unit_dc/test_skip_copyin.py` — 18 tests covering all five
conditions, the skip-set membership rules (structurally, so a too-wide set fails
loudly — verified by mutation), the coupled/non-separable randc path, and a
switch-on-vs-switch-off stimulus-identity check over 7 class shapes.
Full `ve/unit` + `ve/unit_dc` on both back-ends, plus `test_rand_mode` and
`test_random_dist` (excluded from the standard slice) run explicitly. XCHECK
soak clean apart from the known pre-existing failure.

<details><summary>original plan text</summary>

`_apply_node` (`src/vsc/dc/solve_view.py:215`) writes **every** field's current
instance value into the model on every solve. For an enabled rand field this is
pure waste: we write the previous solution into the model so the solver can
immediately overwrite it. 40.6% of the budget before the `__int__` fix; 17.6%
after.

Implementation:
- [ ] Precompute, once per type in `build_solve_node`
      (`solve_view.py:97`), a **copy-in list**: the fields that genuinely must be
      refreshed from the instance each solve — every non-rand field, every field
      referenced by a constraint as an input, array *size* fields, and composite
      children that contain any of the above.
- [ ] Split `_apply_node` into `_apply_fast` (walks only the copy-in list) and
      the existing full path. Select the full path whenever the instance has
      `_vsc_rand_mode` or `_vsc_constraint_mode` set, or the type is flagged
      non-eligible. Fast path is the common case; correctness always has a
      fallback.
- [ ] Rand-size arrays: elements past the solved `size` are not written back, but
      they *are* variables in the problem. Confirm no path reads a stale element,
      or keep rand-size arrays on the full path (cheap, and removes the class of
      bug entirely). Prefer the conservative option first; relax only with a test.
- [ ] Enum fields/arrays go through `EnumInfo` conversion on copy-in
      (`solve_view.py:246-268`) — same rule applies (enabled rand enum ⇒ skip) but
      the conversion is where a latent bug would be silent, so cover it
      explicitly.

**Correctness conditions to state and test explicitly:**
1. A rand field with `rand_mode(False)` becomes a constant at its current
   value — it **must** be copied in. (Handled by routing to the full path.)
2. A non-rand field read by a constraint must be copied in. (It is in the list.)
3. On solve failure the model keeps stale values, but nothing is written back —
   no visible change.
4. A `pre_randomize` hook that mutates a field: vdc calls `get_solve_model`
   (hence `_apply_node`) **before** `do_randomize` runs the hooks
   (`rand_class.py:105`, `randomizer.py:989`), so such a mutation is already not
   seen by the solver today. Add a test that **documents current behaviour**, so
   this step cannot be blamed for a pre-existing wart — and file the wart
   separately.
5. The Tier-A plan-cache freshness signature must not depend on a rand field's
   stale copied-in value. Verify before landing; if it does, that dependency is a
   bug in its own right.

**Validation:**
- [ ] new tests for each of the five conditions above
- [ ] re-randomize-the-same-object tests (this is where the two prior plan-cache
      reuse bugs lived — priority zeroing and the assumption mask)
- [ ] nested composite + composite-array + rand-size-array cases
- [ ] `ve/unit_dc` full, `ve/unit` full, both backends
- [ ] distribution gates unchanged (a copy-in change must not be able to shift a
      distribution; if it does, something reads a stale value)

</details>

---

### S1.4 — Pay-per-use housekeeping walks

Five unconditional O(n) tree walks totalling **53.6 µs = 32%** of the post-fix
budget, every one a semantic no-op for a type like `arr128`. This is the largest
remaining item after S1.2 and also the **least mechanical** — treat each walk
separately, land separately.

Per-type capability flags, computed once (in `type_model` / `build_solve_node`)
and cached: `has_soft`, `has_user_hooks`, `has_dist`, `has_composites`,
`may_override_constraints`.

| # | walk | site | skip condition | confidence |
|---|---|---|---|---|
| C1 | `clear_soft_priority.clear(f)` + per-constraint | `randomizer.py:975,979,995` | type has no soft constraints anywhere in its tree | **high** |
| C2 | `ConstraintOverrideRollbackVisitor.rollback(fm)` | `randomizer.py:1142` | nothing installed an override this solve — make the installer set a flag rather than inferring it | **high** (flag is exact) |
| C3 | `pre_randomize` / `post_randomize` walks | `randomizer.py:989,1146` | **not skippable as-is** — `post_randomize` is what drives vdc writeback via `rand_if` (`solve_view.py:90`). Replace with a direct per-type writeback over a flat precomputed list, then skip the generic walk when the type has no user hooks. | medium |
| C4 | `set_used_rand(True,0)` … `set_used_rand(False,0)` | `randomizer.py:978`, `589/622/674` | set/clear toggle pair; on a Tier-A plan-cache hit `RandInfoBuilder` is skipped, so nothing between the two observes the flag. **Verify that claim before acting on it** — if anything else reads `used_rand`, this does not land. | low — investigate first |

Implementation notes:
- C2's flag must be set by the code that *installs* an override, not inferred
  from structure. Inference here is exactly how a silent-wrong bug gets written.
- C3 is the one that changes control flow rather than skipping work. The
  writeback must still run *before* the user `post_randomize` hook so hook edits
  stick (`solve_view.py:78-80`). Keep that ordering contract in a test.
- C4 gets an investigation task first and an implementation task only if the
  investigation comes back clean. It is acceptable for C4 to end as "not safe,
  documented why."

**Validation:**
- [ ] soft-constraint suite (all shapes, both paths — this is where DSE-3 found
      two repeated-randomize reuse bugs; re-randomize coverage is mandatory)
- [ ] `constraint_mode` / `rand_mode` toggle tests, including toggling *between*
      randomizes of the same object
- [ ] `pre_randomize`/`post_randomize` hook ordering and edit-stickiness tests,
      at every nesting level
- [ ] `foreach` / array-expansion override + rollback tests
- [ ] full `ve/unit` + `ve/unit_dc`, both backends, plus XCHECK

---

### S1.5 — Re-measure and decide  *(the gate)*

- [ ] Re-run `bench_stage1.py`; update `benchmarks/RESULTS.md` and
      `benchmarks/RESULTS_constrainedrandom.md`
- [ ] Re-run the phase attribution and publish an updated §7b-style table into
      the findings doc
- [ ] Re-measure the **read side** (field access after randomize) to confirm
      Stage 1 changed nothing there
- [ ] Apply the parent plan's §3 gate: within ~1.3× of the 64 556/s ceiling ⇒ the
      representation redesign is not worth the disruption; well short ⇒ proceed
      to R1

---

### S1.6 — Optional, only if it falls out cheaply: `randomize_n`

`solver_solve_n` is wired (`lib.py:221`, `zsp_search.c:1056`) and unused by
`randomize()`. There is a fixed ~40–55 µs/randomize cost independent of problem
size, so a batch entry point helps every workload, and §7a concluded the
shared-buffer idea's *real* home is batch solve into an N×M matrix rather than
single-solve readback (where it is worth ~0.31% over S1.2).

This is additive public API and therefore touches the parent plan's feedback
question #6 (batch API shape). **Prototype only in Stage 1; do not fix the public
signature** until that question has been asked.

---

### S1.7 — Narrow the plan-cache freshness signature  *(new; found by S1.1)*

Not in the original plan. The harness found it, and it is the largest single
win Stage 1 has available on a non-array workload.

Mutating **any** non-rand dataclass field between solves invalidates the Tier-A
plan cache, whether or not a constraint references it:

| hook writes | solves/sec |
|---|---:|
| a non-rand *field* (`self.seen = self.a`) | 11 982 |
| a plain attribute (`self._seen = self.a`) | 91 195 |
| nothing (no hook) | 85 530 |

**7.6×.** Attribution confirms the mechanism: on the invalidating class,
`randinfo_build` runs on every solve (1.00 calls/solve) and 73% of the budget is
the rebuild it gates; on the non-invalidating class neither appears.

Cause: the plan's `field_state` snapshot (`randomizer.py`, the plan-cache build
block) records `(f, f.is_used_rand, int(f.get_val()))` for **every** field in
`bound_m`. Correct but over-conservative — only a non-rand field that a
constraint actually *reads* can change the solution.

- [ ] Restrict the `field_state` snapshot to non-rand fields referenced by some
      constraint in the plan. This is **the same set S1.3 computes** for its
      copy-in list, so build it once and share it.
- [ ] `is_used_rand` must stay in the signature for *every* field — a
      `rand_mode` toggle changes the partitioning regardless of value.
- [ ] The referenced-set must be derived from the **post-expansion** constraint
      set, and must include fields read by array-size expressions and by `dist`
      / rangelist scopes.

**Validation:**
- [ ] a non-rand field read by a constraint, mutated between randomizes, still
      invalidates (the whole point — a test that fails loudly if the set is too
      narrow)
- [ ] `rand_mode`/`constraint_mode` toggles between randomizes still invalidate
- [ ] the `knob` workload recovers toward the `hooks` number
- [ ] full suites both front-ends × both back-ends

Why this matters beyond a benchmark: "mutate a non-rand field, re-randomize" is
the config/knob pattern, and it is one of the lifecycle dimensions the parent
plan's §5 says any representation must be measured on. A 7.6× cliff sitting on
that dimension would contaminate every comparison the parent plan wants to make.

---

## 2. Sequencing

```
S1.0 validate __int__ fix  ──►  S1.1 harness + baseline
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
              S1.2 bulk readback            S1.3 skip copy-in
                    └───────────────┬───────────────┘
                                    ▼
                         S1.4 walks: C1, C2 → C3 → C4?
                                    ▼
                          S1.5 re-measure + GATE
                                    ▼
                          S1.6 randomize_n (prototype)
```

S1.2 and S1.3 are independent (different files, different phases) and can be
built in either order. S1.4's sub-steps are sequenced by confidence.

S1.7 was added after S1.1; it depends on S1.3's referenced-field analysis, so it
lands after S1.3 and before S1.5.

---

## 3. Validation policy (applies to every step)

1. **Both front-ends, both back-ends.** `ve/unit` and `ve/unit_dc` × dv-solve and
   boolector. Several of these changes are in shared model-layer code; "vdc-only"
   is a claim the suites have to confirm.
2. **XCHECK differential run** against boolector on each step. It is the
   soundness story and it reads values — every step here touches value movement.
3. **Distribution gates unchanged.** No step may buy speed with distribution.
   Note D1 (the alignment collapse) is a *pre-existing* failure and is not in
   Stage 1's scope; the gate is "no delta", not "passes".
4. **Re-randomize coverage is mandatory,** not optional. Both known plan-cache
   bugs were second-randomize bugs; three of the four workstreams touch state
   reused across solves.
5. **ASAN** on any step that changes pointer or buffer handling (S1.2, S1.6).
6. **Kill-switch honoured**: with all `VSC_S1_*` off, behaviour and timing must
   match the pre-Stage-1 tree. That is the bisection tool and the rollback.
7. **CI caveat:** CI runs only `ve/unit`, installs dv-solve from upstream
   `origin/main`, and does not run `ve/unit_dc`. Any C-side change (S1.2, S1.6)
   must be pushed upstream for CI to see it; `ve/unit_dc` regressions will not be
   caught by CI and must be run locally before each commit.

---

## 4. Risks

| risk | mitigation |
|---|---|
| A skipped walk is a no-op for the benchmark types but load-bearing for a feature the benchmarks don't use | per-type capability flags derived from structure, full path always available, feature-specific suites in the validation list for every walk |
| Silent-wrong rather than crash — the worst failure mode here, and the one the C-side bugs already exhibited | XCHECK on every step; bulk-vs-scalar equivalence test; distribution gates as a no-delta check |
| Classic front-end regressions from shared-layer edits | classic suites on both backends are a gate for every step, not a final check |
| Stage 1 lands the easy 2×, motivation to finish the analysis evaporates, and the parent plan's gate is never actually applied | S1.5 is a numbered deliverable with its own checklist, not an epilogue |
| C4 (`set_used_rand`) is investigated indefinitely | timeboxed; "not safe, documented why" is an acceptable outcome |
| Opportunity cost against the distribution (D1) and coverage work that gate publication | Stage 1 is the cheap half of the parent plan by design; if it exceeds its estimate, stop at S1.5 and re-plan |

---

## 5. Definition of done

- [ ] All of S1.0–S1.5 landed or explicitly declined with a recorded reason
- [ ] `arr128` ≥ 13 000 solves/sec, no regression on any other workload
- [ ] Zero behavioural delta across `ve/unit` and `ve/unit_dc` on both backends
- [ ] `benchmarks/RESULTS.md` and the findings doc updated with post-Stage-1
      attribution
- [ ] The parent plan's §3 gate applied in writing, with the decision recorded
