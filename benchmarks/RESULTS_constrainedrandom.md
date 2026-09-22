# constrainedrandom vs pyvsc — features and speed

A three-way comparison prompted by [constrainedrandom](https://github.com/will-keen/constrainedrandom)'s
claim of being 40–200× faster than pyvsc.

**Configurations**

| tag | what |
|---|---|
| `cr` | constrainedrandom 1.3.0 — `python-constraint` CSP for small domains, random-sample-and-retry otherwise |
| `vsc/btor` | pyvsc classic front-end (`@vsc.randobj`) + Boolector — "stock pyvsc", the thing their claim is against |
| `vdc/dvs` | pyvsc dataclass front-end (`vsc.dc`) + dv-solve native back-end — the new stack |

**Patterns**: `warm` = one object re-randomized (constrainedrandom's own benchmark
pattern); `cold` = fresh object per randomize (the UVM sequence-item / generator
pattern). Both matter; they rank differently.

Reproduce:
```
PYTHONPATH=src:benchmarks python benchmarks/bench_constrainedrandom.py
PYTHONPATH=src:benchmarks python benchmarks/bench_cr_quality.py
```
(`constrainedrandom` must be importable.) Machine/run dependent — ratios are the
durable signal. Every cell is validated against its own constraints on up to 300
samples before being timed, so a fast-but-wrong result cannot win.

---

## 0. First: three defects in their benchmark suite

All three were verified against **stock pyvsc 0.9.5 installed from PyPI**, so
they are not artifacts of this working tree. Each is corrected in our
transcription so that all three configurations solve the *same* problem.

1. **`VSCRandListSumZero` — the pyvsc baseline does not solve the constraint.**
   Their model writes `sum(self.listvar) == 0`. Python's builtin `sum()` builds
   an expression pyvsc silently discards; **193/200 baseline solutions violate
   `sum == 0`**. The working idiom is `self.listvar.sum == 0`. Their "20×
   faster" on this case is measured against a baseline solving an
   *unconstrained* problem — which makes the pyvsc side do *less* work, so the
   direction of the error flatters neither party cleanly, but the comparison is
   not valid as published.

2. **`VSCIn` — the two models are not equivalent.** Their constrainedrandom
   model constrains `b != 0`; the pyvsc model it is timed against constrains
   `c != 0`. The published version genuinely emits `c == 0` solutions
   (29/3000 measured). It also writes `b in range(c, d)` (half-open) against
   pyvsc's `rng(c, d)` (inclusive).

3. **`VSCInstr` — constrainedrandom solves a strictly harder problem.** The
   guard `imm0 + src0_value <= 0xFFFFFFFF` is a **tautology** in both pyvsc
   front-ends (32-bit arithmetic wraps), but a real constraint in
   constrainedrandom's Python-bignum lambda. ~99/200 pyvsc solutions overflow
   32 bits. This one is arguably pyvsc's semantics being correct-for-SV and
   their lambda being correct-for-intent; either way the models differ.

None of this makes the headline claim wrong. It is substantially right.

---

## 1. Is the 40–200× claim true? Yes.

Against stock pyvsc, on their own workloads, corrected:

| suite / pattern | `cr` vs `vsc/btor`, geo-mean |
|---|---:|
| their suite, cold | **26×** |
| their suite, warm | **57×** |
| broader suite, cold | **193×** |
| broader suite, warm | **426×** |

Per-workload it ranges from **8×** (`in_kw`) to **1834×** (`arr128`). The claim
is real and, on array-shaped workloads, understated.

## 2. How much does the new stack close?

> **Re-measured 2026-09-22**, after the Stage 1 overhead removal
> (`doc/notes/vdc_stage1_impl_plan.md`), the T0 no-solver tier, and the
> symbolic-rangelist plan-cache fix (S1.7b). The previous tables in this section
> were recorded before all three and are superseded; the older `vsc/btor` column
> also predates the `ValueScalar.__int__` fix, which affects both back-ends.

`vdc/dvs` vs `vsc/btor` is now **40–440×** across these workloads.

`vdc/dvs` vs `cr` geo-mean:

| suite / pattern | before | **now** |
|---|---:|---:|
| their suite, warm | 0.8× | **3.1×** |
| their suite, cold | 2.5× | **5.2×** |
| broader suite, warm | 0.2× | **0.5×** |
| broader suite, cold | 0.4× | **1.0×** |

**On constrainedrandom's own benchmark suite the new stack is now faster than
constrainedrandom** — 3.1× warm, 5.2× cold, geo-mean. On the broader suite it is
at parity cold and still behind warm, entirely because of the loose-constraint
workloads where sample-and-retry is near-free.

### Where each one wins

| new stack wins | ratio (`vdc/dvs` ÷ `cr`) | why |
|---|---:|---|
| `tight` (narrow feasible region) | **∞** — cr fails outright | retry can't find it |
| `listuniq` (unique over 10 elems) | 13.8–18.4× | global constraint, retry degrades |
| `in_kw` (symbolic range endpoints) | 1.1× warm, **14.4× cold** | `b ∈ [c,d]` with `c,d` rand |
| `listsum` (sum == 0) | 8.3–11.7× | global constraint |
| `packet16` cold | 2.2× | realistic mixed sequence item |
| `ldinstr` | 1.8–2.1× | mixed field/range constraints |
| `arr128` | 1.7–2.1× | **flipped** — was 0.12×, now T0 draws directly |
| `alu` cold | 1.7× | — |
| `arr32` warm | 1.2× | **flipped** — was 0.13× |

| constrainedrandom wins | ratio | why |
|---|---:|---|
| `dist` | 5–10× | weighted draw is one `random.choices` call |
| `alu` warm, `nested` warm | 3× | loose constraints, high retry hit-rate |
| `wide32/64` | 1.1–2× | 32/64-bit unconstrained draw |
| `basic` warm | 1.6× | 8-bit `a<b`, 50% hit rate |

The pattern still holds and is now sharper: **constrainedrandom wins whenever
sample-and-retry has a decent hit rate; the solver stack wins whenever the
constraint actually binds** — and since T0 landed, the cases where it *doesn't*
bind no longer call a solver at all, which is why the array workloads flipped.

### Full tables (2026-09-22)

```
## their suite -- warm                           ## their suite -- cold
workload  |     cr | vsc/btor | vdc/dvs          workload  |     cr | vsc/btor | vdc/dvs
basic     | 205421 |     1522 |  132502          basic     |  84101 |     1228 |   87330
in_kw     |  84093 |      856 |   93282          in_kw     |   4367 |      737 |   63046
ldinstr   |  57417 |      913 |  104001          ldinstr   |  33516 |      763 |   71451
listsum   |   8866 |      231 |  103744          listsum   |   8547 |      221 |   70800
listuniq  |   3581 |      330 |   65859          listuniq  |   3523 |      308 |   48529
geo vdc:cr                        3.1x           geo vdc:cr                        5.2x

## broad -- warm                                 ## broad -- cold
wide32    | 263841 |     1106 |  143871          wide32    | 103818 |      931 |   91468
wide64    | 277015 |      938 |  145730          wide64    | 106902 |      809 |   91689
tight     | RandErr|     1250 |   10177          tight     | RandErr|      995 |    9542
alu       | 360174 |      942 |  115144          alu       |  43866 |      790 |   74905
dist      | 491609 |     2819 |   68794          dist      | 232439 |     1921 |   51664
arr32     | 127947 |     1380 |  149405          arr32     | 100402 |     1009 |   93972
arr128    |  37447 |      350 |   77053          arr128    |  34641 |      310 |   58495
packet16  | 161749 |     3580 |  133726          packet16  |  36704 |     2175 |   81336
nested    | 386078 |     6815 |  112798          nested    |  92494 |     1992 |   71054
geo vdc:cr                        0.5x           geo vdc:cr                        1.0x
```
(solves/sec; `RandErr` = constrainedrandom raised `RandomizationError`. Every
cell is validated against its own constraints on up to 300 samples before being
timed.)

> **`tight` reads slower than the older table (52 312 → 10 177) — that is not a
> regression from this work.** It reproduces identically with every Stage 1
> switch *and* T0 disabled. It is the cost of the alignment-sampler fix recorded
> in §3 below, which traded throughput on that shape for a distribution that is
> not collapsed onto one value. Correct and slower beats fast and wrong.

---

## 3. Speed isn't the only axis — solution quality

A randomizer that is fast *because* it samples-and-retries explores the space
differently. Measured, not assumed (`bench_cr_quality.py`):

**Distribution of `a` under `a < b`** (uniform-over-solutions ⇒ mean ≈ 85):

| | mean |
|---|---:|
| `cr` | **82.9** (closest to ideal) |
| `vdc/dvs` | 95.8 |
| `vsc/btor` | 101.8 |

constrainedrandom is *better* here.

**Value spread over `a inside {1,2,[100:200]}`**, 4000 samples, 103 legal values:

| | distinct | max count |
|---|---:|---:|
| `cr` | 103/103 | 59 |
| `vdc/dvs` | 103/103 | 55 |
| `vsc/btor` | 103/103 | **1003** ← Boolector is badly clumped |

**Weighted `dist` fidelity** (declared 10/80/10): all three land within ~1%.
No differentiator.

**But — a real dv-solve distribution bug.** On the `tight` workload
(`addr` in a 4 KB window, 64-byte aligned, 64 legal solutions), 5000 samples:

| | distinct | max share |
|---|---:|---:|
| `cr` (hand-tuned domain) | 64/64 | 1.9% |
| `vsc/btor` | 63/64 | 47.3% |
| `vdc/dvs` | 57/64 | **93.6%** |

Isolated by shape (`bench_cr_distshape.py`): a plain range is fine (2521
distinct values, 0.2% max share), but **adding any alignment/divisibility term
(`% 64 == 0` or `& 0x3F == 0`) collapses dv-solve onto the range's lowest legal
value ~93% of the time.** Boolector degrades too (14% max share) but far less.
This is a genuine sampler defect, not a benchmark artifact.

### Root cause and fix (LANDED)

`zsp_search.c`: when a plain value decision conflicts on an interior value, the
search opens a reversible two-way split around it — and **always explored the
lower half first**. Where the feasible set is sparse and enforced by a
*propagator* (not by holes), every random pick conflicts and re-restricts the
domain to `[dlo, val-1]`, so the walk descends monotonically and lands on the
smallest feasible value nearly every draw.

(The sibling bias — domains expressed as *holes*, e.g. `inside {0,255}`
returning 0 ~99% of the time — had already been fixed in
`_pick_avoiding_holes`. This is the propagator-enforced counterpart, which
never reaches the hole list at all.)

Fix: choose the first half at random, **size-weighted**, in diversity mode
(`opts->seed != 0`). Seed 0 (BMC/decision) keeps the old deterministic
lower-first order so those solves stay reproducible. Kill-switch:
`ZSP_SPLIT_RANDOM=0`.

| shape (5000 draws) | before: distinct / max share | after |
|---|---|---|
| range + `% 64 == 0` | 52/64, **93.0%** | **64/64, 2.0%** |
| range + `& 0x3F == 0` | 52/64, **92.1%** | **64/64, 2.1%** |
| relational (benchmark's `tight`) | 55/64, **92.2%** | **64/64, 5.9%** |

(Uniform would be 1.56%.) dv-solve is now *better than Boolector* on all three
shapes. Probe 3 `tight` spread: 57/64 → **61/64**.

**The cost, stated plainly:** `tight` throughput drops **5×** (52 312 → 9 113
warm; 42 019 → 8 603 cold). The old code was fast on that shape precisely
*because* it collapsed — it found the domain minimum immediately and stopped.
Real search for a diverse answer costs more. Every other workload is neutral
(0.96–1.04×, i.e. noise), and `tight` at ~8 600/s is still **7.5× faster than
Boolector** on the same problem, and constrainedrandom cannot solve it at all.
Trading 5× on one constraint shape for stimulus that isn't 93% one value is the
right call, but it is a trade.

**Regression status:** `ve/unit` 541 passed / 1 failed, `ve/unit_dc` 283 passed
— identical to the pre-change baseline. dv-solve's own suite: 46 failed / 2416
passed **both with and without the fix** (A/B'd via the kill-switch); those 46
are pre-existing and environment-related (missing `bitwuzla`, verilator
fixtures). The one `ve/unit` failure,
`test_dvsolve_array_native::test_tc2_fixed_product`, was verified to fail on the
original unmodified sources too — it is pre-existing and unrelated.

---

## 4. A dv-solve performance anomaly

`in_kw` is the one workload where `vdc/dvs` is **slower warm than cold** —
4 186/s vs 33 192/s, a 0.13× ratio. Every other workload is ≥1.2× warm, and
Boolector is 1.00× on the same model, so it is dv-solve-path specific. The
distinguishing feature of `in_kw` is a rangelist with **rand endpoints**
(`b inside [rng(c,d)]`). Re-randomizing the same object with that shape appears
to fall off the plan cache *and* land on a path slower than a cold build.

---

## 5. Feature comparison

Verified against the installed packages, not from documentation claims.
constrainedrandom's entire public API is 8 methods: `add_rand_var`,
`add_constraint`, `randomize`, `get_results`, `set_random`, `set_solver_mode`,
`pre_randomize`, `post_randomize`.

| capability | constrainedrandom | pyvsc classic | pyvsc dataclass |
|---|---|---|---|
| constraint form | Python lambdas returning `bool` | operator-overloaded expressions | AST-parsed real Python expressions |
| implication / if-else | `if` inside the lambda | `if_then`/`else_then`/`implies` | same |
| set membership | `in` in a lambda, or `domain=` | `rangelist`/`rng` | `.inside(rangelist(…))` |
| **symbolic range endpoints** | lambda + retry only | ✅ | ✅ |
| weighted distribution | weighted `domain=` dict (a *sampler*) | `dist`/`weight` (a *constraint*) | same |
| **soft constraints** | ❌ | ✅ | ✅ |
| ordering (`solve…before`) | `order=` | `solve_order` | `solve_order` |
| `unique` | `list_constraints=[unique]` | ✅ | ✅ |
| `foreach` over arrays | per-element `constraints=` | ✅ | ✅ |
| random array length | `rand_length=` | `randsz_list_t` | ✅ |
| **`randc` (cyclic)** | ❌ | ❌ | ✅ |
| **object composition / nested rand objects** | ❌ — flatten by hand | ✅ | ✅ |
| inline constraints | `randomize(with_constraints=…)` | `randomize_with` | `randomize_with` |
| **`constraint_mode` / `rand_mode`** | ❌ | ✅ | ✅ |
| **functional coverage (covergroup)** | ❌ | ✅ | ✅ |
| **UNSAT detection / diagnosis** | ❌ — retries, then `RandomizationError` | ✅ | ✅ |
| type/IDE support | strings for variable names | strings | ✅ real annotations |

Two structural gaps matter most:

- **No object composition.** Every sub-object must be flattened into the
  parent's namespace by hand. For layered UVM sequence items this is the
  difference between a library you can build a testbench on and one you can't.
- **No UNSAT detection.** constrainedrandom cannot distinguish "this constraint
  set is unsatisfiable" from "I got unlucky 100 times". `RandomizationError`
  means both. For a DV user debugging a constraint conflict at 3am, that's the
  single most valuable diagnostic and it isn't there.

Also note the `nested` benchmark caveat: declared naively (an equality between
two 16-bit vars) constrainedrandom runs at **17 solves/sec** because the 65536
domain exceeds `max_domain_size` (1024) and it falls back to retry with
probability 2⁻¹⁶. To get the 393k/s number above, the constraint has to be
hand-converted into a derived variable — i.e. *the user solves the constraint,
not the library*. The same applies to `tight`: constrainedrandom can only do it
if you hand-compute the feasible domain. Those hand-tunings are the numbers
reported, to show the library at its best, but they are not declarative
constrained-random.

---

## 6. Takeaway

- The 40–200× claim against stock pyvsc is **true**, and their benchmark suite
  has three defects that a fix would not rescue pyvsc from.
- The dv-solve dataclass stack recovers **20–220×** of that gap, and wins
  outright on genuinely constrained problems (`unique`, `sum`, symbolic ranges,
  narrow feasible regions where constrainedrandom fails outright).
- It still **loses** to constrainedrandom on loosely-constrained and
  array-shaped workloads, sometimes by 10×. That gap is a Python-overhead gap,
  not a solver gap: on `arr128` the native solve is a small fraction of
  `randomize()`.
- constrainedrandom's speed comes from being a *sampler with a CSP fallback*,
  not a solver. That is a legitimate and well-executed design point, and it
  wins a lot of real workloads. Its cost is paid in features (no composition,
  no soft, no coverage, no cyclic, no modes) and in the cases where it simply
  can't converge.
- Two actionable defects found on our side: the **alignment-constraint
  distribution collapse** (dv-solve returned the same value 93% of the time) —
  **now fixed**, at the cost of 5× throughput on that one shape — and the
  **`in_kw` warm-slower-than-cold** anomaly, still open.
