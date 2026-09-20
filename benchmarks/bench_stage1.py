"""Stage 1 overhead-removal ladder: throughput + per-phase attribution.

Tracks doc/notes/vdc_stage1_impl_plan.md. Two things it must do that the
existing benchmarks do not:

  1. **Attribute** a randomize() to its phases with real timers (not cProfile,
     which distorted these measurements by up to ~2.5x).
  2. **Bisect** — each Stage 1 step is behind a switch in
     ``vsc.model.opt_flags``, so the ladder can be re-derived on demand and any
     regression pinned to one step.

Headline timing and attribution are taken in *separate processes*: the phase
timers themselves cost ~100ns per instrumented site, which is a few percent of
the target budget, so they must not contaminate the headline number.

Run:
    PYTHONPATH=src:benchmarks python benchmarks/bench_stage1.py            # ladder
    PYTHONPATH=src:benchmarks python benchmarks/bench_stage1.py --attrib   # phases
    PYTHONPATH=src:benchmarks python benchmarks/bench_stage1.py --all      # both
    ... [--scale S] [--workload NAME]
"""
import argparse
import math
import os
import random
import subprocess
import sys
import time

import vsc
from vsc.model import opt_flags, phase_timers as PT

from _stage1_workloads import WORKLOADS, TARGET_WORKLOAD, TARGET_SPS

# The switches in the order they land, so the ladder rows mean something.
LADDER = [
    ("baseline (all off)",  dict(BULK_READBACK=False, SKIP_COPYIN=False, LAZY_WALKS=False)),
    ("+ S1.2 bulk readback", dict(BULK_READBACK=True,  SKIP_COPYIN=False, LAZY_WALKS=False)),
    ("+ S1.3 skip copy-in",  dict(BULK_READBACK=True,  SKIP_COPYIN=True,  LAZY_WALKS=False)),
    ("+ S1.4 lazy walks",    dict(BULK_READBACK=True,  SKIP_COPYIN=True,  LAZY_WALKS=True)),
]


def _set(cfg):
    for k, v in cfg.items():
        setattr(opt_flags, k, v)


def t_warm(cls, n):
    """Reuse one object, randomize n times (the plan-cache-warm path Stage 1
    targets). Returns seconds."""
    random.seed(0)
    o = cls()
    for _ in range(5):
        o.randomize()
    t0 = time.perf_counter()
    for _ in range(n):
        o.randomize()
    return time.perf_counter() - t0


def t_cold(cls, n):
    """Fresh object each solve (the generator / UVM sequence-item pattern)."""
    random.seed(0)
    cls().randomize()          # warm the per-type caches
    t0 = time.perf_counter()
    for _ in range(n):
        cls().randomize()
    return time.perf_counter() - t0


def _fmt(x):
    return format(x, ",.0f").replace(",", " ") if x >= 1000 else "%.0f" % x


def _select(names):
    if not names:
        return WORKLOADS
    sel = [w for w in WORKLOADS if w[0] in names]
    missing = set(names) - {w[0] for w in sel}
    if missing:
        sys.exit("unknown workload(s): %s" % ", ".join(sorted(missing)))
    return sel


# ---------------------------------------------------------------------------
# Ladder
# ---------------------------------------------------------------------------

def ladder(workloads, scale, timer, label, reps=3):
    print("## %s  (solves/sec, dv-solve; best of %d interleaved reps)"
          % (label, reps))
    hdr = "%-9s" % "workload" + "".join("| %14s " % n for n, _ in LADDER) + "| total"
    print(hdr)
    print("-" * len(hdr))
    speedups = []
    for name, cls, n in workloads:
        n = max(20, int(n * scale))
        # Sweep the configs `reps` times and keep the best per config. A single
        # sequential sweep is biased: later configs run on a hotter cache, which
        # showed up as a spurious ~1.3x on `basic` when every switch was still a
        # no-op. Interleaving + best-of cancels monotonic drift.
        best = [0.0] * len(LADDER)
        for _ in range(reps):
            for i, (_, cfg) in enumerate(LADDER):
                _set(cfg)
                dt = timer(cls, n)
                sps = n / dt if dt > 0 else float("inf")
                best[i] = max(best[i], sps)
        row = best
        sp = row[-1] / row[0] if row[0] > 0 else float("nan")
        speedups.append(sp)
        flag = "" if sp >= 0.97 else "   <-- REGRESSION"
        print("%-9s" % name + "".join("| %14s " % _fmt(v) for v in row)
              + "| %5.2fx%s" % (sp, flag))
    geo = math.exp(sum(math.log(s) for s in speedups if s > 0) / len(speedups))
    print("-" * len(hdr))
    print("%-9s" % "geo-mean" + " " * (17 * len(LADDER)) + "| %5.2fx" % geo)
    print()
    _set(dict(BULK_READBACK=True, SKIP_COPYIN=True, LAZY_WALKS=True))


def target_check(scale):
    """Report the Stage 1 headline target explicitly, pass or fail."""
    wl = [w for w in WORKLOADS if w[0] == TARGET_WORKLOAD][0]
    n = max(20, int(wl[2] * scale))
    _set(dict(BULK_READBACK=True, SKIP_COPYIN=True, LAZY_WALKS=True))
    dt = t_warm(wl[1], n)
    sps = n / dt
    print("## Stage 1 target: %s warm >= %s solves/sec" % (TARGET_WORKLOAD, _fmt(TARGET_SPS)))
    print("   measured: %s solves/sec (%.1f us/solve)  -->  %s"
          % (_fmt(sps), 1e6 * dt / n, "PASS" if sps >= TARGET_SPS else "NOT YET"))
    print()


# ---------------------------------------------------------------------------
# Phase attribution (runs with VSC_PHASE_TIMERS=1)
# ---------------------------------------------------------------------------

def attribution(workloads, scale, timer, label):
    if not PT.ENABLED:
        sys.exit("attribution requires VSC_PHASE_TIMERS=1 (use --all, which "
                 "re-execs, or set it yourself)")
    for name, cls, n in workloads:
        n = max(20, int(n * scale))
        _set(dict(BULK_READBACK=True, SKIP_COPYIN=True, LAZY_WALKS=True))
        timer(cls, n)               # warm, discard
        PT.reset()
        dt = timer(cls, n)
        print("## %s  %s  (%d solves, %.1f us/solve total)"
              % (label, name, n, 1e6 * dt / n))
        print("%-16s | %9s | %7s | %6s" % ("phase", "us/solve", "pct", "calls"))
        print("-" * 48)
        for pname, _tot, per, pct, calls in PT.report(n, dt):
            print("%-16s | %9.2f | %6.1f%% | %6.2f" % (pname, per, pct, calls))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--workload", action="append", default=[])
    ap.add_argument("--attrib", action="store_true", help="phase attribution only")
    ap.add_argument("--all", action="store_true", help="ladder, then attribution "
                    "in a second process")
    ap.add_argument("--cold", action="store_true", help="create-many instead of reuse")
    ap.add_argument("--reps", type=int, default=3,
                    help="interleaved sweeps per workload (best-of)")
    args = ap.parse_args()

    vsc.set_solver_backend("dv-solve")
    workloads = _select(args.workload)
    timer, label = (t_cold, "COLD (create-many)") if args.cold else (t_warm, "WARM (reuse)")

    if args.attrib:
        attribution(workloads, args.scale, timer, label)
        return

    print("# Stage 1 ladder — doc/notes/vdc_stage1_impl_plan.md")
    print("# switches: %s\n" % opt_flags.snapshot())
    ladder(workloads, args.scale, timer, label, reps=args.reps)
    target_check(args.scale)

    if args.all:
        # Separate process: the phase timers cost enough to move the headline.
        env = dict(os.environ, VSC_PHASE_TIMERS="1")
        argv = [sys.executable, __file__, "--attrib", "--scale", str(args.scale)]
        if args.cold:
            argv.append("--cold")
        for w in args.workload:
            argv += ["--workload", w]
        subprocess.run(argv, env=env, check=False)


if __name__ == "__main__":
    main()
