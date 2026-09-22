# Known failures — triage

Opened 2026-09-22, while tidying up after Stage 1
(`doc/notes/vdc_stage1_impl_plan.md`). Both entries were carried along as
"pre-existing failures" through every Stage 1 validation run; this is the
triage that should have happened when they were first noticed.

Both reproduce on a **clean checkout at `8d01f0b`** (the commit before any
Stage 1 work), verified in a detached worktree, with every `VSC_S1_*` switch
off and with the plan cache and merged solve disabled. Neither is caused by
Stage 1.

---

## KF-1 — `if/else` constraints: dv-solve returns models that violate them

**FIXED 2026-09-22.** Root cause and fix at the end of this entry. The XCHECK
soak is green for the first time (211 passed). The description below is kept as
written, because the diagnosis it records is what led to the cause.

**Severity: high. This is a soundness bug in the default back-end, and it is
silent.** It produces illegal stimulus with no error, no warning, and no
fallback event. It is only visible if you run with `VSC_DVSOLVE_XCHECK=1`,
which is off by default.

Surfaces as `ve/unit/test_randomization.py::TestRandomization::test_simple`
under the XCHECK soak (`ve/run_xcheck_soak.sh`):

```
XCheckMismatch: dv-solve produced a model that VIOLATES the constraints
(Boolector finds the problem SAT but rejects this model) — a mis-encoding.
  a = 23274 (width=16, signed=False)
  b = 0     (width=8,  signed=False)
  c = 1     (width=2,  signed=False)
  d = 0     (width=1,  signed=False)
```

### Reproduction

```python
@vsc.randobj
class S(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(8); self.b = vsc.rand_bit_t(8)
        self.c = vsc.rand_bit_t(2); self.d = vsc.rand_bit_t(1)

    @vsc.constraint
    def k(self):
        with vsc.if_then(self.a < self.b):
            self.c < self.d
        with vsc.else_then():
            self.c == self.d
```

Randomize 2000 times and check each model:

| back-end | models violating the constraint |
|---|---|
| dv-solve | **1263 / 2000 (63%)** |
| boolector | 0 / 2000 |

Every violation is in the **else** branch: `a >= b` (so `c == d` is required)
with `c != d`.

### What the failure rate depends on

Same shape, varying only the *then*-branch, 600 samples each:

| then-branch | satisfying assignments | else-branch violations |
|---|---|---|
| `c >= 0` (loose) | all | 2 / 600 |
| `c >= 2` | half | 151 / 600 |
| `c < d` (c is 2-bit, d is 1-bit) | one (`c=0,d=1`) | 367 / 600 |
| `c > 3` (c is 2-bit) | none — UNSAT | 425 / 600 |

**The more constrained the then-branch, the less the else-branch is enforced.**
`if_then` with no `else_then` is clean (0/800). An `if/else` whose then-branch
is loose is nearly clean.

That shape points at the reified guard: the then-branch implication appears to
drive the guard variable, while the else-branch implication is not
symmetrically linked to it — so the search satisfies the then-side, lands on a
guard value that selects the *else* side, and nothing re-checks. Mixed operand
widths are **not** the cause (same-width reproduces identically).

Related prior work in the same family: dv-solve `bcea612` *"Propagate both
operands of a reified comparison, not one (G13)"*, and the F-E3 note in
`dvsolve_backend.py` that an aux-lifted logical-combination implication guard
makes the primary's disjunction propagation unsound — which is why
`requires_bvsat` exists. **This constraint is not being routed there:** the
fallback tally over 50 randomizes is empty (`{}`), so the primary engine is
answering it directly and confidently.

### KF-1b — the safety net that would have caught this is not wired

`packages/dv-solve/src/dv_solve/ctx.py` has `validate_model()`:

> *"Re-evaluate every constraint in the problem against the current assignment.
> Returns the number of violations... the post-solve net for the class of bug
> where a constraint is dropped at compile time and the search then satisfies
> only what it was given."*

`grep -rn validate_model src/vsc/` returns **nothing**. It is never called.

This is the systemic half of KF-1 and is worth fixing independently of the
encoding bug: a debug/CI mode that calls `validate_model` after every
`SOLVE_OK` would have turned a silent wrong answer into a loud one at the
source, rather than leaving it to an XCHECK run nobody does by default.

**DONE 2026-09-22.** `VSC_DVSOLVE_VALIDATE=1` now re-checks every `SOLVE_OK`
model on both solve paths (merged and per-RandSet) and raises
`ModelValidationError`; CI sets it on the dv-solve leg and the XCHECK soak.
Confirmed against the unfixed engine: KF-1 went from a silent 63% wrong-answer
rate to an immediate loud failure on the first bad model, with **no oracle** —
which is the property XCHECK does not have.

#### What wiring it up turned up

The validator could not have been switched on as it stood: it reported **15
tests' worth of violations on models that were entirely correct**. Its
expression evaluator disagreed with the engine in four ways, each found by
dumping the offending constraint tree (`solver_validate_model` takes a `FILE*`
for exactly this) and reading the values back:

| symptom | cause |
|---|---|
| `z = -2` "violates" `z < 0` | relational ops compared raw bit patterns, ignoring signedness |
| aligned address "violates" `addr % (1 << size)` | shift result masked to the *shift amount's* width, so `1 << 12` was 0 |
| `k=8, a=16` "violates" `a == k * 2` | arithmetic evaluated at `max(operand widths)` — 4 bits — instead of the context width |
| `755852753` "violates" `<= 3718135548` | mixed signed/unsigned comparison treated as signed |

The third is the real one: bit width in SystemVerilog is **context-determined**,
not a bottom-up property of each node. Every operand is evaluated at the width of
the widest operand in the whole expression, *including the far side of the
comparison* — which is why `r == a + b` over three u8s must wrap to 44 while
`a == k * 2` with a u4 `k` must not wrap at all. `_max_width()` now computes that
context and `_eval()` threads it down (shift amounts stay self-determined, per
the SV rule). Signedness follows the matching SV rule: signed only if every
width-bearing operand is signed.

After those four fixes both suites are clean under validation (`ve/unit` 579
passed, `ve/unit_dc` 441 passed; only KF-2 below still fails, unrelated), and the
validator still catches KF-1 on the unfixed engine. A validator that invents
violations is worse than none, since the whole point is to be trusted in CI.

### Root cause

Not the guard linkage. **A zero-extend wrapper on an OR leaf.**

pyvsc emits a width-mismatched comparison with the narrower side wrapped:
`c == zero_extend(d)` for 2-bit `c` and 1-bit `d`. The whole if/else compiles to

```
AND( OR(NOT(a<b), c<d),  OR(a<b, c == zext(d)) )
```

`_classify_or_leaf` in `zsp_compile.c` accepted a zero-extend wrapper on a
**var-const** leaf but not on a **var-var** one — that case used bare `_is_var`
on both sides. So the second leaf was rejected, `_flatten_or` failed for the
whole disjunction, and compilation fell through to the `_bool_to_var`
Boolean-guard fallback — the one the translator's own comments (F-E3) describe
as having unsound primary propagation.

That explains every observation in the table above. Only the *else* comparison
was width-mismatched, so only the else clause was lost. The looser the
then-branch, the more often the search could satisfy the surviving clause
without ever pinning the guard, which is why the violation rate tracked
then-branch restrictiveness. And nothing was routed to BV-SAT because from the
compiler's point of view nothing had failed.

Isolating it took building the same problem twice against the raw dv-solve API:
by hand it was clean at 0/400, and the only difference from what pyvsc built was
that one `expr_extend` — adding it reproduced 236/400 immediately.

### Fix

`_or_leaf_var()` in `zsp_compile.c` — strip a zero-extend wrapper on either side
of a var-var OR leaf, guarded so it is only done where it cannot change the
value: not a sign-extend, not a signed var, and `from_bits` not below the var's
own width. Under those conditions the extended value *is* the var's value, so
comparing at the wider width is exactly comparing the values, which is what the
DisjClause var-var propagator computes.

Verified: 0 violations in 2000 draws (was 1263), all four then-branch variants
clean, both branches still exercised, and the XCHECK soak green at 211 passed.
Regression tests in `ve/unit/test_dvsolve_ifelse_soundness.py` — two of the four
fail on the unfixed engine, which is the point.

---

## KF-2 — `arr.product` is not served natively

**Severity: low. Not a correctness bug** — the answer is correct, it is just
not produced by the native engine.

`ve/unit/test_dvsolve_array_native.py::TestDvSolveArrayNative::test_tc2_fixed_product`

```python
s.arr = vsc.rand_list_t(vsc.rand_bit_t(8), 8)
s.arr.product == 4
```

The test wraps randomization in a `_no_fallback()` guard that makes any
fall-through to Boolector raise, so the failure message is
`"dv-solve fell back to Boolector for a RandSet (array not native?)"`.

Fallback tally for one randomize: `{'bvsat-sat-deferred': 1}` — the primary
engine could not solve the multiply chain, BV-SAT proved it SAT, and value
serving was deferred to the distribution-preserving fallback. The model is
valid (`[2,1,2,1,1,1,1,1]`, product 4).

So this is a **native-coverage gap on `product`**, tracked by a test that
asserts native handling. It fails identically under both `VSC_SOLVER` legs
because the test forces dv-solve itself.

### Suggested handling

Either close the gap (native `product` serving) or mark the test `xfail` with a
reference to this entry, so the suite is green and the gap stays visible. It
should not keep failing silently as "the known one".
