"""Broad optimization comparison — the pyvsc-side reconstruction optimizations
(Stage 1 declared-only bounds + array plan-cache reuse + whole-problem merged
solve) ON vs OFF, across diverse workloads, for both the create-many (cold) and
reuse (warm) patterns on the dv-solve back-end.

Toggles the flags in-process so the same live objects are timed both ways:
  - declared-only bounds : DvSolveBackend.derives_bounds
  - array plan cache     : randomizer._ARRAY_PLAN_CACHE
  - whole-problem merge  : randomizer._MERGE_ENABLED

Run:  PYTHONPATH=src:benchmarks python benchmarks/bench_optimizations.py [scale]
"""
import random
import sys
import time

import vsc
import vsc.model.randomizer as RZ
from vsc.model.solver.dvsolve_backend import DvSolveBackend
from _bench_workloads import WORKLOADS


def _set_opts(on):
    RZ._ARRAY_PLAN_CACHE = on
    RZ._MERGE_ENABLED = on
    DvSolveBackend.derives_bounds = on


def t_cold(cls, n):
    """Create-many: fresh object + randomize once, n times (dataclass shares the
    type model, so the plan cache hits across instances)."""
    random.seed(0)
    t0 = time.perf_counter()
    for _ in range(n):
        cls().randomize()
    return time.perf_counter() - t0


def t_warm(cls, n):
    """Reuse one object, randomize n times."""
    random.seed(0)
    o = cls()
    for _ in range(5):
        o.randomize()
    t0 = time.perf_counter()
    for _ in range(n):
        o.randomize()
    return time.perf_counter() - t0


def _sps(dt, n):
    return n / dt if dt > 0 else float("inf")


def _fmt(x):
    if x >= 1000:
        return format(x, ",.0f").replace(",", " ")
    return "%.0f" % x


def run(scenario, timer, n_for):
    print("## %s  (dv-solve; solves/sec; OFF = pre-optimization baseline)" % scenario)
    print("%-9s | %10s | %10s | %7s" % ("workload", "OFF", "ON", "speedup"))
    print("-" * 46)
    speedups = []
    for name, cls in WORKLOADS:
        n = n_for(name)
        _set_opts(False)
        off = _sps(timer(cls, n), n)
        _set_opts(True)
        on = _sps(timer(cls, n), n)
        sp = on / off if off > 0 else float("nan")
        speedups.append(sp)
        flag = "" if sp >= 0.95 else "  <-- REGRESSION"
        print("%-9s | %10s | %10s | %6.2fx%s" % (name, _fmt(off), _fmt(on), sp, flag))
    import math
    geo = math.exp(sum(math.log(s) for s in speedups if s > 0) / len(speedups))
    print("-" * 46)
    print("%-9s | %10s | %10s | %6.2fx" % ("geo-mean", "", "", geo))
    print()


def main():
    scale = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    vsc.set_solver_backend("dv-solve")

    # Per-workload iteration counts (cheaper workloads get more iterations).
    base = {
        "scalar": 3000, "alu": 3000, "wide64": 3000, "dist": 3000,
        "nested": 3000, "packet16": 1500,
        "arr8": 2000, "arr32": 1200, "arr128": 400, "arr256": 200, "arr512": 100,
    }

    def n_for(name):
        return max(20, int(base[name] * scale))

    print("# Optimization comparison: reconstruction optimizations ON vs OFF")
    print("# (declared-only bounds + array plan cache + whole-problem merge)")
    print("# backend=dv-solve  scale=%g\n" % scale)

    run("A. CREATE-MANY (fresh object each solve — generator/UVM pattern)",
        t_cold, n_for)
    run("B. REUSE (one object re-randomized — warm)", t_warm, n_for)

    _set_opts(True)   # restore defaults


if __name__ == "__main__":
    main()
