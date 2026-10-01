"""Per-stage attribution of ``randomize()`` for the vdc + dv-solve stack.

Answers "where does the time actually go?" for each workload, so every later
optimization phase is measured against a recorded number instead of a guess.

Two numbers per workload:
  * a **headline** rate, measured in a clean pass with the phase timers OFF (they
    cost ~100ns per instrumentation site, which is not free at these rates);
  * a **breakdown**, measured in a second pass with them ON.

The breakdown percentages are of the instrumented pass, so they are internally
consistent even though that pass is slightly slower than the headline.

Phases nest: ``solve``/``readback`` happen inside the back-end call. ``(unattributed)``
is whatever ``randomize()`` spent outside every instrumentation site -- model
construction, expression evaluation, Python call overhead.

Cold-path stages (``bounds_1`` .. ``randinfo_build``) are skipped entirely on a
plan-cache hit, so in the warm pattern they should be ~0 for a cacheable model.
A warm run that still shows them is falling off the plan cache -- which is itself
the finding.

Run:
  PYTHONPATH=src:benchmarks python benchmarks/bench_stage_profile.py [--quick]
  PYTHONPATH=src:benchmarks python benchmarks/bench_stage_profile.py --only arr128
"""
import argparse
import os
import sys
import time

import vsc
from vsc.model import phase_timers as PT

import _cr_workloads as W

DEFAULT_TMAX = 3.0


def _run(cls, warm, tmax, cap=None):
    """Randomize until `tmax` elapses (or `cap` iterations); return (n, seconds)."""
    obj = cls() if warm else None
    n = 0
    t0 = time.perf_counter()
    while True:
        (obj if warm else cls()).randomize()
        n += 1
        el = time.perf_counter() - t0
        if el >= tmax or (cap is not None and n >= cap):
            return n, el


def profile(cls, warm, tmax):
    """Headline rate (timers off) + per-stage breakdown (timers on).

    ``PT.set_enabled`` is what makes the first pass genuinely uninstrumented:
    ``PT.ENABLED`` is bound at import, so before it existed the headline pass was
    silently timed too whenever ``VSC_PHASE_TIMERS`` was set, costing ~2x.
    """
    want_detail = PT.ENABLED
    prev = PT.set_enabled(False)
    try:
        n, el = _run(cls, warm, tmax)
    finally:
        PT.set_enabled(prev)
    headline = n / el

    if not want_detail:
        return headline, None

    PT.reset()
    n2, el2 = _run(cls, warm, tmax, cap=max(n // 4, 50))
    return headline, (PT.report(n2, el2), n2, el2)


def fmt_breakdown(rep, indent="      "):
    out = []
    for name, _total_us, us_per, pct, calls in rep:
        if pct < 0.05 and us_per < 0.05:
            continue
        out.append("%s%-20s %8.2f us/solve  %5.1f%%  %.2f calls" %
                   (indent, name, us_per, pct, calls))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="shorter timing windows")
    ap.add_argument("--only", default=None, help="run a single workload by name")
    ap.add_argument("--pattern", default="both", choices=("warm", "cold", "both"))
    args = ap.parse_args()

    tmax = 0.8 if args.quick else DEFAULT_TMAX

    if not PT.ENABLED:
        print("NOTE: VSC_PHASE_TIMERS is not set -- headline rates only, no "
              "breakdown.\n      Re-run with VSC_PHASE_TIMERS=1 for attribution.\n")

    vsc.set_solver_backend("dv-solve")

    workloads = W.ALL
    if args.only:
        workloads = [w for w in workloads if w.name == args.only]
        if not workloads:
            print("no such workload: %s" % args.only)
            print("available: %s" % ", ".join(w.name for w in W.ALL))
            return 1

    patterns = (("warm", True), ("cold", False))
    if args.pattern != "both":
        patterns = [p for p in patterns if p[0] == args.pattern]

    print("vdc front-end + dv-solve back-end\n")
    for wl in workloads:
        if wl.vdc is None:
            continue
        print("=" * 72)
        print("%s" % wl.name)
        for pname, warm in patterns:
            try:
                headline, detail = profile(wl.vdc, warm, tmax)
            except Exception as e:
                print("  %-5s ERROR %s: %s" % (pname, type(e).__name__, str(e)[:80]))
                continue
            print("  %-5s %9.1f solves/s  (%7.2f us/solve)" %
                  (pname, headline, 1e6 / headline))
            if detail is not None:
                rep, n2, el2 = detail
                print(fmt_breakdown(rep))
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
