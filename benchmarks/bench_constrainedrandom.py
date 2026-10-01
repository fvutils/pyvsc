"""Three-way comparison: constrainedrandom vs stock pyvsc vs dv-solve pyvsc.

Configurations
  cr        constrainedrandom (RandObj)                    -- python-constraint + retry
  vsc/btor  pyvsc classic front-end, boolector back-end    -- "stock pyvsc"
  vdc/dvs   pyvsc dataclass front-end, dv-solve back-end   -- the new stack

Patterns
  warm  one object, randomize() N times     -- constrainedrandom's own benchmark pattern
  cold  fresh object per randomize()        -- the UVM sequence-item / generator pattern

Every configuration is validated on a sample of solutions before it is timed,
so a fast-but-wrong or fast-but-degenerate result cannot win.

Run:
  PYTHONPATH=src:benchmarks python benchmarks/bench_constrainedrandom.py [--quick]
(constrainedrandom must be importable.)
"""
import argparse
import math
import random
import sys
import time

import vsc
from constrainedrandom import RandomizationError

import _cr_workloads as W

VALIDATE_SAMPLES = 300
VALIDATE_TMAX = 3.0
DEFAULT_TMAX = 5.0


# ---------------------------------------------------------------------------
# result extraction
# ---------------------------------------------------------------------------

def extract(obj):
    """Normalize a randomized object to {field: plain-python-value}."""
    if hasattr(obj, "get_results"):            # constrainedrandom
        return obj.get_results()
    out = {}
    for k, v in vars(obj).items():
        if k.startswith("_") or k == "tname" or callable(v):
            continue
        if isinstance(v, (int, list)):
            out[k] = v
        elif hasattr(v, "__iter__"):           # vsc.rand_list_t
            out[k] = [int(x) for x in v]
        elif type(v).__name__ == "ValueInt":
            out[k] = int(v)
        else:
            out[k] = v                         # sub-object
    return out


# ---------------------------------------------------------------------------
# timing
# ---------------------------------------------------------------------------

class Cell(object):
    def __init__(self, hz=None, status="ok", n=0):
        self.hz = hz
        self.status = status
        self.n = n

    def __bool__(self):
        return self.hz is not None


def validate(make, check, warm):
    """Check as many solutions as VALIDATE_SAMPLES / VALIDATE_TMAX allow.

    The sample has to be reasonably large: a model that violates its own
    constraints ~1% of the time (which one of the transcribed workloads did)
    slips through a 25-sample check most of the time."""
    obj = make() if warm else None
    t0 = time.perf_counter()
    for _ in range(VALIDATE_SAMPLES):
        o = obj if warm else make()
        o.randomize()
        check(extract(o))
        if time.perf_counter() - t0 > VALIDATE_TMAX:
            break


def time_cell(make, check, n, t_max, warm):
    try:
        validate(make, check, warm)
    except RandomizationError as e:
        return Cell(status="RandErr")
    except AssertionError:
        return Cell(status="WRONG")
    except Exception as e:                      # noqa: BLE001 - report, don't crash
        return Cell(status=type(e).__name__[:12])

    random.seed(0)
    obj = make() if warm else None
    if warm:
        for _ in range(3):
            obj.randomize()
    done = 0
    t0 = time.perf_counter()
    try:
        while done < n:
            chunk = min(25, n - done)
            for _ in range(chunk):
                if warm:
                    obj.randomize()
                else:
                    make().randomize()
            done += chunk
            if time.perf_counter() - t0 > t_max:
                break
    except Exception as e:                      # noqa: BLE001
        return Cell(status=type(e).__name__[:12])
    dt = time.perf_counter() - t0
    return Cell(hz=done / dt if dt > 0 else float("inf"), n=done)


# ---------------------------------------------------------------------------
# configurations
# ---------------------------------------------------------------------------

def run_config(cfg, wl, n, t_max, warm):
    if cfg == "cr":
        return time_cell(wl.cr, wl.check_cr, n, t_max, warm)
    if cfg == "vsc/btor":
        vsc.set_solver_backend("boolector")
        try:
            return time_cell(wl.vsc, wl.check_vsc, n, t_max, warm)
        finally:
            vsc.set_solver_backend(None)
    if cfg == "vdc/dvs":
        vsc.set_solver_backend("dv-solve")
        try:
            return time_cell(wl.vdc, wl.check_vdc, n, t_max, warm)
        finally:
            vsc.set_solver_backend(None)
    raise ValueError(cfg)


CONFIGS = ["cr", "vsc/btor", "vdc/dvs"]


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def fmt_hz(c):
    if not c:
        return c.status
    if c.hz >= 1000:
        return format(c.hz, ",.0f").replace(",", " ")
    return "%.1f" % c.hz


def ratio(num, den):
    if not num or not den or den.hz == 0:
        return "-"
    return "%.1fx" % (num.hz / den.hz)


def geomean(vals):
    vals = [v for v in vals if v and v > 0]
    if not vals:
        return float("nan")
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def run_suite(title, workloads, scale, t_max, warm):
    mode = "warm (reuse one object)" if warm else "cold (fresh object each solve)"
    print("## %s -- %s" % (title, mode))
    print("solves/sec; higher is better\n")
    hdr = "%-9s | %10s | %10s | %10s | %9s | %9s" % (
        "workload", "cr", "vsc/btor", "vdc/dvs", "cr:vsc", "vdc:cr")
    print(hdr)
    print("-" * len(hdr))
    r_cr_vsc, r_vdc_cr = [], []
    rows = []
    for wl in workloads:
        n = max(25, int(wl.n * scale))
        cells = {cfg: run_config(cfg, wl, n, t_max, warm) for cfg in CONFIGS}
        rows.append((wl, cells))
        c, v, d = cells["cr"], cells["vsc/btor"], cells["vdc/dvs"]
        if c and v:
            r_cr_vsc.append(c.hz / v.hz)
        if c and d:
            r_vdc_cr.append(d.hz / c.hz)
        print("%-9s | %10s | %10s | %10s | %9s | %9s" % (
            wl.name, fmt_hz(c), fmt_hz(v), fmt_hz(d), ratio(c, v), ratio(d, c)))
    print("-" * len(hdr))
    print("%-9s | %10s | %10s | %10s | %8.1fx | %8.1fx" % (
        "geo-mean", "", "", "", geomean(r_cr_vsc), geomean(r_vdc_cr)))
    print()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--tmax", type=float, default=DEFAULT_TMAX)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated workload names")
    args = ap.parse_args()
    if args.quick:
        args.scale = 0.1
        args.tmax = 1.5

    suites = [("constrainedrandom's own benchmark suite", W.CR_SUITE),
              ("Broader suite", W.BROAD_SUITE)]
    if args.only:
        want = set(args.only.split(","))
        suites = [(t, [w for w in wls if w.name in want]) for t, wls in suites]
        suites = [(t, wls) for t, wls in suites if wls]

    print("# constrainedrandom vs pyvsc(boolector) vs pyvsc-dataclass(dv-solve)")
    print("# python %s  scale=%g  tmax=%gs  validate=%d samples/cell\n"
          % (sys.version.split()[0], args.scale, args.tmax, VALIDATE_SAMPLES))
    print("Legend: `RandErr` = constrainedrandom gave up (RandomizationError);")
    print("        `WRONG` = produced a solution violating its own constraints.\n")

    for warm in (True, False):
        for title, wls in suites:
            run_suite(title, wls, args.scale, args.tmax, warm)


if __name__ == "__main__":
    main()
