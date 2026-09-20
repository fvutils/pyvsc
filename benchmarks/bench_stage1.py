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
_OFF = dict(BULK_READBACK=False, SKIP_COPYIN=False, LAZY_WALKS=False,
            NARROW_PLAN_SIG=False)
LADDER = [
    ("baseline (all off)",   dict(_OFF)),
    ("+ S1.2 bulk readback", dict(_OFF, BULK_READBACK=True)),
    ("+ S1.3 skip copy-in",  dict(_OFF, BULK_READBACK=True, SKIP_COPYIN=True)),
    ("+ S1.4 lazy walks",    dict(_OFF, BULK_READBACK=True, SKIP_COPYIN=True,
                                  LAZY_WALKS=True)),
    ("+ S1.7 narrow sig",    dict(BULK_READBACK=True, SKIP_COPYIN=True,
                                  LAZY_WALKS=True, NARROW_PLAN_SIG=True)),
]


def _set(cfg):
    for k, v in cfg.items():
        setattr(opt_flags, k, v)


def _reset_type_caches(cls):
    """Drop the per-type solve model (and with it the cached Tier-A plan).

    Required between ladder configurations: S1.7 changes how a plan's freshness
    signature is *built*, and `is_fresh` then reads the stored tuples — so a plan
    built under one setting keeps that shape until it is rebuilt. Without this
    reset the S1.7 column measured whatever the previous column left cached,
    which showed up as `knob` reporting 83 644 solves/sec in the "all off"
    column instead of its true 13 150.
    """
    if "_vsc_solve_model" in cls.__dict__:
        delattr(cls, "_vsc_solve_model")


def t_warm(cls, n):
    """Reuse one object, randomize n times (the plan-cache-warm path Stage 1
    targets). Returns seconds."""
    random.seed(0)
    _reset_type_caches(cls)
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
    _reset_type_caches(cls)
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
    _set(LADDER[-1][1])


def target_check(scale):
    """Report the Stage 1 headline target explicitly, pass or fail."""
    wl = [w for w in WORKLOADS if w[0] == TARGET_WORKLOAD][0]
    n = max(20, int(wl[2] * scale))
    _set(LADDER[-1][1])
    dt = t_warm(wl[1], n)
    sps = n / dt
    print("## Stage 1 target: %s warm >= %s solves/sec" % (TARGET_WORKLOAD, _fmt(TARGET_SPS)))
    print("   measured: %s solves/sec (%.1f us/solve)  -->  %s"
          % (_fmt(sps), 1e6 * dt / n, "PASS" if sps >= TARGET_SPS else "NOT YET"))
    print()


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------

def read_side(workloads, scale, reps=3):
    """Field-access cost *after* randomize().

    The parent plan (`vdc_value_representation_plan.md` §2) calls the read side
    "the trap": a change that makes randomize() fast and `obj.field` slow can be
    a net loss, because user code reads fields in drivers, scoreboards and
    coverage sampling. Stage 1 deliberately does not touch how values are
    stored, so the expected result here is *no change* — and that is worth
    measuring rather than asserting.

    Reported separately from throughput, never folded into a geo-mean.
    """
    print("## READ SIDE — ns per field read, after randomize()")
    print("%-9s | %14s | %14s | %7s" % ("workload", "all off", "all on", "ratio"))
    print("-" * 52)
    for name, cls, n in workloads:
        iters = max(200, int(n * scale))
        res = []
        for cfg in (LADDER[0][1], LADDER[-1][1]):
            best = 0.0
            for _ in range(reps):
                _set(cfg)
                _reset_type_caches(cls)
                o = cls()
                o.randomize()
                names = [f.name for f in o._get_type_model().fields]
                t0 = time.perf_counter()
                for _ in range(iters):
                    for fn in names:
                        getattr(o, fn)
                dt = time.perf_counter() - t0
                rate = (iters * len(names)) / dt
                best = max(best, rate)
            res.append(1e9 / best)          # ns per read
        ratio = res[1] / res[0] if res[0] else float("nan")
        flag = "" if ratio <= 1.05 else "   <-- READ REGRESSION"
        print("%-9s | %14.1f | %14.1f | %6.2fx%s"
              % (name, res[0], res[1], ratio, flag))
    print()
    _set(LADDER[-1][1])


# ---------------------------------------------------------------------------
# Phase attribution (runs with VSC_PHASE_TIMERS=1)
# ---------------------------------------------------------------------------

def attribution(workloads, scale, timer, label):
    if not PT.ENABLED:
        sys.exit("attribution requires VSC_PHASE_TIMERS=1 (use --all, which "
                 "re-execs, or set it yourself)")
    for name, cls, n in workloads:
        n = max(20, int(n * scale))
        _set(LADDER[-1][1])
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
    ap.add_argument("--read", action="store_true", help="read-side cost only")
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

    if args.read:
        read_side(workloads, args.scale, reps=args.reps)
        return

    print("# Stage 1 ladder — doc/notes/vdc_stage1_impl_plan.md")
    print("# switches: %s\n" % opt_flags.snapshot())
    ladder(workloads, args.scale, timer, label, reps=args.reps)
    target_check(args.scale)
    read_side(workloads, args.scale, reps=args.reps)

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
