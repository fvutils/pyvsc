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

### Suggested handling

1. Wire `validate_model` behind an env flag and turn it on in CI. Cheap, and it
   bounds the blast radius of this whole class.
2. Fix the else-branch guard linkage in the native engine, or — as an immediate
   stopgap — mark `if/else` with a constrained then-branch as
   `requires_bvsat`, which is the existing mechanism for exactly this.
3. Add a regression test asserting the constraint holds over N draws (the
   current test only checks that randomize succeeds).

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
