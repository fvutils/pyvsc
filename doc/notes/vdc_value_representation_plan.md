# vdc value & variable representation — research, benchmark, and feedback plan

Status: **proposal for review** · drafted 2026-09-20 · high-level by intent —
each section becomes its own design doc as we commit to it.

Scope: how the **dataclass front-end (`vsc.dc` / `vdc`)** represents variable
values at rest, during a solve, and on the way in and out of the native solver.

**Explicitly out of scope: the classic `@vsc.randobj` front-end and the
boolector path.** They stay as they are. That is not a concession — it is what
makes this tractable: classic remains the compatibility surface and the XCHECK
oracle, so vdc is free to change its representation without a deprecation
cycle for existing users.

---

## 1. Why now

`doc/notes/dv_solve_boundary_overhead_findings.md` measured the current cost
model on `arr128`. The short version:

- The native solve is **~12%** of `randomize()`.
- Value representation accounts for most of the rest: three traversals of the
  same values per solve (copy-in → solve → readback → copy-out), a `ValueScalar`
  box per field per traversal, and five unconditional model walks.
- A one-line fix to `ValueScalar.__int__` (an `int`-subclass return that put
  CPython on the deprecated-conversion path) was worth **1.46×** on its own —
  which is the tell that we are paying representation costs, not solver costs.
- constrainedrandom, measured on the same box, makes **the same order of Python
  calls** (1 696 vs ~2 900) but each is **~5× cheaper**, because its state *is*
  the Python attribute. It has no model/value duality to maintain.

The conclusion driving this plan: **our overhead is the price of a general
value model maintained unconditionally, not the price of solving.** Before
optimising further inside the current representation, it is worth asking what
representation we would choose if we were choosing today.

---

## 2. The design question

Three axes, roughly independent:

**A. Where does the truth live?**
1. *Python attribute is truth; model is scratch* — today. Requires sync both
   directions every solve.
2. *Model is truth; attribute is a view* — one representation, but every user
   read goes through an indirection.
3. *A flat per-instance slot buffer is truth* — attributes and model are both
   views over it; the native solver writes into it directly.

**B. Boxed or unboxed?** Today every value is a `ValueScalar` object carrying
`.v`. Width and signedness are per-*type* facts that could live in static
layout metadata instead of travelling with each value.

**C. Eager or lazy materialisation?** In the generator pattern (build item →
randomize → send → discard) the consumer often reads a handful of fields. We
currently materialise every field as a Python `int` on every solve.

Option **A.3 + B-unboxed** is the interesting corner, because it makes the
native boundary nearly free as a *side effect* rather than as an optimisation:
if the instance's storage is already a flat `int64` buffer with a per-type
layout, the solver writes the answer in place and there is no readback at all.
It also makes batch solving (`solver_solve_n` into an `N × M` matrix) the
natural shape rather than a bolt-on. The per-type solve-model cache vdc already
has is the precondition that makes a stable per-type layout possible.

**But the read side is the trap.** A representation that makes `randomize()`
fast and `obj.field` slow can be a net loss — user code reads fields in
scoreboards, drivers, coverage sampling, and `post_randomize`. Any candidate
must be evaluated on *both* sides. This is the single most important thing the
benchmark plan has to get right.

---

## 3. Stage 0 — establish the non-breaking ceiling first (decision gate)

**Do not commit to a re-representation before knowing what the incremental path
yields.** The findings doc estimates a ladder of non-breaking fixes (bulk
readback; skip copy-in for enabled rand fields; make the five housekeeping walks
pay-per-use via per-type flags) reaching roughly parity with constrainedrandom
*without* changing any modeler-visible behaviour.

Stage 0 is: land those, re-measure, and only then decide whether the remaining
gap justifies a representation change.

**Gate:** if the non-breaking path lands within ~1.3× of the §5 ceiling, the
redesign is probably not worth the disruption and this plan reduces to a
cleanup. If it plateaus well short, proceed to R1.

This ordering also de-risks the research: the Stage-0 work produces the
instrumentation and workload harness that R2 needs anyway.

---

## 4. Research plan

**R1 — Design-space map + throwaway spike.**
Enumerate candidate models (A.1/A.2/A.3 × boxed/unboxed × eager/lazy), then
build a *deliberately throwaway* prototype of the most promising one or two —
enough to get honest upper bounds on both randomize throughput and field-read
cost. No integration, no tests, no correctness. The goal is a number, not code.
Kill criteria stated up front.

**R2 — Primitive micro-benchmarks.**
Cost of each representation primitive in isolation, on the Python versions we
support: plain dataclass attribute read/write; `__slots__` attribute;
descriptor-mediated access; `memoryview` slot read; buffer→`list` materialisation
(already measured: `memoryview.tolist()` is at the Python-int allocation floor,
and `list(buf)` is 14× worse); array-view object vs real `list`. These numbers
decide A and B more than any architectural argument will.

**R3 — Semantics inventory.**
Everything that currently touches a value, catalogued before anything moves:
constraint evaluation in Python (soft relaxation, randc candidate filtering,
const-constraint checking), coverage sampling, `pre`/`post_randomize`, inline
`randomize_with`, `rand_mode`/`constraint_mode`, nested composites and composite
arrays, enums, `>64`-bit fields, XCHECK readback, UCIS export, and the dataclass
contract itself (`repr`, `==`, `asdict`, `copy`, pickle). This inventory is the
real scope of the change; the representation is the easy part.

**R4 — Native interface contract.**
If storage becomes a buffer the solver writes into, the invariants from
`dv_solve_boundary_overhead_findings.md` §7a become load-bearing rather than
optional: compile-time slot mapping, buffer lifetime and pointer typing,
width/signedness settled natively, `>64`-bit opt-out, validity only on
`SOLVE_OK`, no aliasing under parallel partition solving, multi-stage solves
read once. Write these as an explicit contract with a differential test, not as
prose.

---

## 5. Benchmark plan

The existing suites (`benchmarks/RESULTS.md`,
`benchmarks/RESULTS_constrainedrandom.md`) measure `randomize()` throughput.
That is necessary and insufficient for this question.

**Add a representation benchmark measuring the full object lifecycle**, because
that is what a testbench actually does:

| dimension | why |
|---|---|
| **construct** | generator patterns build a fresh item per transaction |
| **randomize** | today's metric |
| **read a few fields** | driver/scoreboard access — the read-side trap |
| **read every field** | serialisation, logging, coverage sampling |
| **mutate a non-rand field, re-randomize** | config/knob pattern |
| **nested + composite-array access** | where indirection costs compound |
| **batch of N** | the `solver_solve_n` shape |

Rules:

- **Report read-side and write-side separately.** A candidate that wins
  randomize and loses field-read must be visible as such, not hidden in a
  geo-mean.
- **Keep constrainedrandom and stock pyvsc as reference columns**, per the
  publishing strategy — and note the finding that cr's throughput is very
  sensitive to declaration style (one list var vs N scalar vars was 10× on the
  same problem), so model it both ways.
- **Correctness gates ride along**: every configuration validates its samples,
  and the distribution gates apply unchanged. A representation change must not
  be able to buy speed with distribution or soundness.
- **Profile-free timing for headline numbers**; cProfile only for attribution.
  The profiler distorted these measurements by ~2.5× in places.

---

## 6. Human-feedback plan

Some of this is invisible to modelers and is ours to decide on measurements
alone. Some of it changes what writing a vdc model *feels like*, and we should
not decide those from a benchmark. The split matters: asking about everything
wastes goodwill, asking about nothing produces an API only we like.

**Decide ourselves (measurement-driven, not modeler-visible):** slot layout,
boxing, native buffer contract, when walks are skipped, batch-solve internals.

**Ask modelers about:**

1. **What is `obj.my_array`?** A real `list`, or a sequence view? This governs
   mutation, slicing, `==`, JSON/`asdict`, and "can I `.append` to it".
2. **Are vdc instances still ordinary dataclasses?** `repr`, `==`, `asdict`,
   `copy`, pickle. Some of these are cheap to keep and some are not.
3. **What is a field's value before the first `randomize()`?** Today's answer
   should be stated and confirmed, not silently changed.
4. **Mutating fields between randomizes** — how freely, and what happens to
   non-rand inputs.
5. **Type-checker visibility.** Does `a: vdc.u8` still read as an `int` to
   mypy/pyright? This was already an acknowledged soft spot for the
   decorator-generated coverage API.
6. **Batch API shape** — `randomize_n(cls, 1000)` returning what, exactly, and
   is a batch of objects or an object-of-arrays more natural?
7. **Appetite for breaking changes in vdc at all**, and on what notice. vdc is
   new and pre-announcement, which is exactly the window where this is cheap —
   but "new" is not "unused".

**How to gather it, cheapest first:**

- **A short written RFC** with 3–5 concrete before/after code snippets — not
  prose about representations. Modelers react to code.
- **Run it past the DatagenDV-shaped use case specifically.** Microsoft
  independently built `@rand_dataclass` over pyvsc, so that paper's authors are
  the closest thing to a target user with published requirements. Their stated
  pain (`rand_*` types awkward outside constraints) is directly about value
  representation.
- **Use the blog series as the channel.** Post 2 covers the dataclass model; an
  RFC box in that post reaches the right audience at the right moment, with no
  extra machinery.
- **A prototype branch people can `pip install`** — only if R1 shows the win is
  large enough to be worth asking for time.
- **A written decision log**, so reversals are cheap and the reasoning survives.

Do **not** block Stage 0 on any of this. Stage 0 changes nothing modelers can
see.

---

## 7. Sequencing and gates

```
Stage 0  non-breaking fixes + harness      ──► GATE: how much gap remains?
   │
   ├─ gap small  ──► stop; write up; fold into W2 and publish
   │
   └─ gap large  ──► R1 spike ──► GATE: does the spike beat Stage 0
                        │                on BOTH read and write sides?
                        ├─ no  ──► stop
                        └─ yes ──► R2/R3/R4 + RFC to modelers
                                      └──► GATE: semantics cost acceptable?
                                                └──► design doc, then build
```

Three explicit stops. The plan should be as willing to conclude "the current
representation is fine once the waste is removed" as to conclude the opposite —
and Stage 0 is deliberately the cheapest way to find out.

---

## 8. Risks

- **Read-side regression.** The biggest. Mitigated by making it a first-class
  benchmark dimension rather than an afterthought.
- **Semantics sprawl.** R3's inventory is the true scope; the representation is
  the small part. If R3 comes back large, that is itself a result.
- **Divergence from classic.** Two front-ends with different value models means
  shared model-layer code (`rand_info_builder`, visitors, coverage) must serve
  both. Some of the recent engine fixes were in exactly that shared layer.
  Quantify the shared-code surface in R3 before committing.
- **XCHECK.** The differential check against boolector is our soundness story
  and it reads values. It must keep working across the change, ideally
  unmodified.
- **Opportunity cost.** This competes with the distribution and coverage work
  that gate publication. Stage 0 is cheap; the redesign is not. Sequencing it
  after those is likely correct.

---

## 9. Open questions for review

1. **Is Stage 0's gate the right one**, or do we already know we want the
   re-representation regardless of what the incremental path yields?
2. **How much breakage is acceptable in vdc**, and does that change after the
   blog series announces it? If the answer is "much less after announcement,"
   that argues for doing R1 sooner rather than later.
3. **Should classic and vdc share the model layer indefinitely?** The answer
   bounds how far vdc's representation can diverge, and it is a strategic
   question, not a technical one.
4. **Is lazy materialisation on the table at all,** or is "after `randomize()`,
   every field is a real Python value" a semantic guarantee we want to keep?
5. **Who are the three modelers we would actually ask?** The feedback plan is
   worth little without names.
