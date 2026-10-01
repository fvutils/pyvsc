"""
Cross-frontend x cross-backend randomization benchmark.

Purpose: show users *why* they'd move backends and *why* they'd move frontends.

  - "Why move backends?"  -> the solver does the heavy lifting; dv-solve vs
    boolector throughput is workload-dependent (sometimes 30x, sometimes <1x).
  - "Why move frontends?" -> the *classic* @vsc.randobj front-end re-elaborates
    the model on EVERY instance (per-instance build_model), while the *dataclass*
    front-end elaborates structure ONCE per type and reuses it. So the front-end
    only matters when you create many objects — the realistic generator / UVM
    sequence-item pattern. That is the headline scenario here.

Three scenarios per (frontend, backend, workload):
  A. per-instance : construct a FRESH object + randomize once, repeatedly
                    (the create-many-items pattern — where the front-end matters).
  B. reuse        : one object, randomize() repeatedly (warm plan cache —
                    both front-ends converge; shows the plan-cache win).
  C. construct    : construct only, no randomize (isolates per-instance build cost).

Classes are defined ONCE (module scope); only object construction happens inside
the timing loops, so we measure construction/solve, not class decoration.

Run:  PYTHONPATH=src python benchmarks/bench_frontends.py [N]
"""
import math
import random
import sys
import time

import vsc
import vsc.dc as vdc


# ==========================================================================
# Workloads — each defined ONCE, both ways.
# ==========================================================================

@vsc.randobj
class C_simple(object):
    def __init__(self):
        self.a = vsc.rand_uint8_t()
        self.b = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        self.a < self.b


@vdc.dataclass
class D_simple(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b


@vsc.randobj
class C_alu(object):
    def __init__(self):
        self.op = vsc.rand_bit_t(4)
        self.a = vsc.rand_uint32_t()
        self.b = vsc.rand_uint32_t()

    @vsc.constraint
    def c(self):
        self.op <= 7
        self.a < self.b
        self.a.inside(vsc.rangelist(1, 2, (100, 200)))


@vdc.dataclass
class D_alu(vdc.RandClass):
    op: vdc.u4 = vdc.rand()
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.op <= 7
        self.a < self.b
        self.a.inside(vdc.rangelist(1, 2, (100, 200)))


@vsc.randobj
class C_array(object):
    def __init__(self):
        self.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

    @vsc.constraint
    def c(self):
        with vsc.foreach(self.arr) as it:
            it > 2
            it < 250


@vdc.dataclass
class D_array(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=8)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


@vsc.randobj
class C_wide(object):
    def __init__(self):
        self.x = vsc.rand_uint64_t()
        self.y = vsc.rand_uint64_t()

    @vsc.constraint
    def c(self):
        self.x < self.y
        self.x > 1000


@vdc.dataclass
class D_wide(vdc.RandClass):
    x: vdc.u64 = vdc.rand()
    y: vdc.u64 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.x < self.y
        self.x > 1000


@vsc.randobj
class C_dist(object):
    def __init__(self):
        self.k = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        vsc.dist(self.k, [
            vsc.weight(0, 10), vsc.weight((1, 3), 80), vsc.weight(4, 10)])


@vdc.dataclass
class D_dist(vdc.RandClass):
    k: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.dist(self.k, [
            vdc.weight(0, 10), vdc.weight((1, 3), 80), vdc.weight(4, 10)])


@vsc.randobj
class C_sub(object):
    def __init__(self):
        self.a = vsc.rand_uint16_t()
        self.b = vsc.rand_uint16_t()


@vsc.randobj
class C_nested(object):
    def __init__(self):
        self.s1 = vsc.rand_attr(C_sub())
        self.s2 = vsc.rand_attr(C_sub())

    @vsc.constraint
    def c(self):
        self.s1.a == self.s2.a


@vdc.dataclass
class D_sub(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()


@vdc.dataclass
class D_nested(vdc.RandClass):
    s1: D_sub = vdc.rand()
    s2: D_sub = vdc.rand()

    @vdc.constraint
    def c(self):
        self.s1.a == self.s2.a


# (name, classic class, dataclass class)
WORKLOADS = [
    ("simple", C_simple, D_simple),
    ("alu",    C_alu,    D_alu),
    ("array8", C_array,  D_array),
    ("wide64", C_wide,   D_wide),
    ("dist",   C_dist,   D_dist),
    ("nested", C_nested, D_nested),
]

BACKENDS = ["dv-solve", "boolector"]
FRONTENDS = ["classic", "dc"]


# ==========================================================================
# Timing scenarios (classes are pre-defined; we only build objects here)
# ==========================================================================

def t_per_instance(cls, n):
    """A: construct a fresh object + randomize once, n times."""
    random.seed(0)
    t0 = time.perf_counter()
    for _ in range(n):
        cls().randomize()
    return time.perf_counter() - t0


def t_reuse(cls, n):
    """B: one object, randomize() n times (warm plan cache)."""
    random.seed(0)
    obj = cls()
    for _ in range(5):
        obj.randomize()
    t0 = time.perf_counter()
    for _ in range(n):
        obj.randomize()
    return time.perf_counter() - t0


def t_construct(cls, n):
    """C: construct only (no randomize), n times."""
    t0 = time.perf_counter()
    for _ in range(n):
        cls()
    return time.perf_counter() - t0


def _sps(dt, n):
    return n / dt if dt > 0 else float("inf")


def geomean(xs):
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else float("nan")


def _fmt(x):
    return format(x, ",.0f").replace(",", " ")


def _backend_available(name):
    try:
        vsc.set_solver_backend(name)
        D_simple().randomize()
        return True
    except Exception:
        return False
    finally:
        vsc.set_solver_backend(None)


def _matrix_table(title, timer, n, cells, results, key):
    print("## %s" % title)
    header = "%-9s" % "workload"
    for fe, be in cells:
        header += " | %15s" % ("%s/%s" % (fe, be))
    print(header)
    print("-" * len(header))
    for wl, cc, dc in WORKLOADS:
        row = "%-9s" % wl
        for fe, be in cells:
            cls = cc if fe == "classic" else dc
            vsc.set_solver_backend(be)
            try:
                sps = _sps(timer(cls, n), n)
                results[(key, wl, fe, be)] = sps
                row += " | %15s" % _fmt(sps)
            except Exception as e:
                results[(key, wl, fe, be)] = None
                row += " | %15s" % ("ERR:" + type(e).__name__)[:15]
            finally:
                vsc.set_solver_backend(None)
        print(row)
    print()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    avail = [b for b in BACKENDS if _backend_available(b)]
    cells = [(fe, be) for be in avail for fe in FRONTENDS]
    results = {}

    print("# Cross-frontend x cross-backend randomization benchmark")
    print("# N=%d per cell; backends: %s" % (n, ", ".join(avail)))
    print("# solves/sec (higher is better)\n")

    _matrix_table("A. PER-INSTANCE  (construct fresh + randomize — the create-many pattern)",
                  t_per_instance, n, cells, results, "inst")
    _matrix_table("B. REUSE  (one object re-randomized — warm plan cache)",
                  t_reuse, n, cells, results, "reuse")
    _matrix_table("C. CONSTRUCT-ONLY  (no randomize — per-instance build cost)",
                  t_construct, n, cells, results, "ctor")

    # ---- Why move FRONTENDS? dc vs classic, same backend ----
    print("## Why move FRONT-ENDS?  dataclass vs classic (>1 = dataclass faster)")
    for be in avail:
        inst = geomean([results[("inst", wl, "dc", be)] / results[("inst", wl, "classic", be)]
                        for wl, _, _ in WORKLOADS
                        if results.get(("inst", wl, "dc", be)) and results.get(("inst", wl, "classic", be))])
        reuse = geomean([results[("reuse", wl, "dc", be)] / results[("reuse", wl, "classic", be)]
                         for wl, _, _ in WORKLOADS
                         if results.get(("reuse", wl, "dc", be)) and results.get(("reuse", wl, "classic", be))])
        ctor = geomean([results[("ctor", wl, "dc", be)] / results[("ctor", wl, "classic", be)]
                        for wl, _, _ in WORKLOADS
                        if results.get(("ctor", wl, "dc", be)) and results.get(("ctor", wl, "classic", be))])
        print("  [%-9s] per-instance %.2fx | reuse %.2fx | construct %.0fx"
              % (be, inst, reuse, ctor))
    print("  => create-many-objects (the common generator pattern): dataclass wins")
    print("     (no per-instance build_model); reuse-one-object: front-ends converge.")
    print()

    # ---- Why move BACKENDS? dv-solve vs boolector, per workload (per-instance) ----
    if "dv-solve" in avail and "boolector" in avail:
        print("## Why move BACK-ENDS?  dv-solve vs boolector (per-instance, dc front-end; >1 = dv-solve faster)")
        ratios = []
        for wl, _, _ in WORKLOADS:
            d = results.get(("inst", wl, "dc", "dv-solve"))
            b = results.get(("inst", wl, "dc", "boolector"))
            if d and b:
                ratios.append(d / b)
                print("  %-9s : %5.1fx %s" % (wl, d / b,
                      "" if d >= b else "(boolector wins)"))
        print("  geo-mean : %.1fx  => backend choice is workload-dependent; pick per workload." % geomean(ratios))
    print()

    # ---- Fastest overall combo per workload (per-instance) ----
    print("## Fastest combo per workload (per-instance)")
    for wl, _, _ in WORKLOADS:
        best = max((c for c in cells if results.get(("inst", wl, c[0], c[1]))),
                   key=lambda c: results[("inst", wl, c[0], c[1])], default=None)
        if best:
            print("  %-9s -> %s/%s  (%s/sec)"
                  % (wl, best[0], best[1], _fmt(results[("inst", wl, best[0], best[1])])))


if __name__ == "__main__":
    main()
