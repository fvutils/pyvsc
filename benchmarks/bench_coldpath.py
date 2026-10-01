"""
Cold-path phase-attribution + size-sweep harness (Stage 0 of the native
full-problem plan — see doc/notes/dv_solve_native_full_problem_plan.md).

Purpose: measure where cold-path `randomize()` time goes as problem SIZE grows,
so the "gate the expensive bound pass" change (Stage 1) can be proven or refuted
before/after. The win is size-dependent: negligible on scalars, large on
array-heavy problems.

Two views:
  A. THROUGHPUT size-sweep — solves/sec, cold (fresh object each solve), for
     scalar / arr[16] / arr[128] / arr[512] and a wide-scalar case.
  B. PHASE ATTRIBUTION — cProfile cumulative time bucketed by pipeline phase
     (VBV / array-expand / RandInfoBuilder / translate / native solve /
     reuse-signature) for one representative large workload.

Run:  PYTHONPATH=src python benchmarks/bench_coldpath.py [scale]
      VSC_SOLVER=dv-solve is forced; pass a backend name as 2nd arg to override.
"""
import cProfile
import pstats
import random
import sys
import time

import vsc
import vsc.dc as vdc


# ==========================================================================
# Size-sweep workloads (dataclass front-end — no per-instance build cost noise)
# ==========================================================================

def make_array_cls(n):
    @vdc.dataclass
    class _A(vdc.RandClass):
        arr: list[vdc.u8] = vdc.rand(size=n)

        @vdc.constraint
        def c(self):
            with vdc.foreach(self.arr) as it:
                it > 2
                it < 250
    _A.__name__ = "arr%d" % n
    return _A


@vdc.dataclass
class Scalar(vdc.RandClass):
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


def make_wide_scalar_cls(n):
    """N independent constrained scalars — stresses per-field bound propagation
    without arrays (each var has an independent range constraint). Uses the
    classic front-end so a Python loop in the constraint body is allowed
    (the dataclass parser is declarative-only)."""
    def __init__(self):
        for i in range(n):
            setattr(self, "v%d" % i, vsc.rand_uint16_t())

    def c(self):
        for i in range(n):
            getattr(self, "v%d" % i) > 10
            getattr(self, "v%d" % i) < 5000
    cls = vsc.randobj(type("wide%d" % n, (object,),
                           {"__init__": __init__, "c": vsc.constraint(c)}))
    return cls


# ==========================================================================
# Timing
# ==========================================================================

def t_cold(cls, n):
    """Construct fresh + randomize once, n times (cold path — no plan-cache reuse
    across instances of a fresh object)."""
    random.seed(0)
    t0 = time.perf_counter()
    for _ in range(n):
        cls().randomize()
    return time.perf_counter() - t0


def _sps(dt, n):
    return n / dt if dt > 0 else float("inf")


def _fmt(x):
    return format(x, ",.0f").replace(",", " ")


# Map source-file basename -> pipeline phase label, for attribution rollup.
_PHASE_FILES = {
    "variable_bound_visitor.py": "VBV (bound analysis)",
    "array_constraint_builder.py": "array-expand",
    "dist_constraint_builder.py": "dist-expand",
    "rand_info_builder.py": "RandInfoBuilder (partition)",
    "dvsolve_expr_translator.py": "translate",
}
# Specific function markers (file:func) for phases that share a file.
_PHASE_FUNCS = {
    ("dvsolve_backend.py", "_solve_and_readback"): "native solve+readback",
    ("dvsolve_backend.py", "_reuse_signature"): "reuse-signature",
    ("dvsolve_backend.py", "_build_and_solve"): "native build+solve",
}


def phase_attribution(cls, n):
    """cProfile a cold loop and roll cumulative time up by pipeline phase."""
    pr = cProfile.Profile()
    random.seed(0)
    pr.enable()
    for _ in range(n):
        cls().randomize()
    pr.disable()
    st = pstats.Stats(pr)
    total = 0.0
    buckets = {}
    for (fpath, line, func), vals in st.stats.items():
        # vals = (cc, nc, tt, ct, callers); ct = cumulative time
        ct = vals[3]
        base = fpath.rsplit("/", 1)[-1]
        if base == "randomizer.py" and func == "do_randomize":
            total = ct
        label = _PHASE_FILES.get(base)
        if label is None:
            label = _PHASE_FUNCS.get((base, func))
        if label is not None:
            # Use the top-level entry point per phase (max cumulative for that
            # label) to avoid double-counting nested frames.
            buckets[label] = max(buckets.get(label, 0.0), ct)
    return total, buckets


# ==========================================================================
# Main
# ==========================================================================

def main():
    scale = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    backend = sys.argv[2] if len(sys.argv) > 2 else "dv-solve"
    vsc.set_solver_backend(backend)

    print("# Cold-path size-sweep + phase attribution")
    print("# backend=%s  scale=%d" % (backend, scale))
    print("# solves/sec (higher is better)\n")

    # ---- A. throughput size-sweep ----
    print("## A. Cold throughput vs size")
    sweep = [
        ("scalar", Scalar, max(1, 2000 // scale) * scale),
        ("arr16", make_array_cls(16), max(1, 800 // scale) * scale),
        ("arr128", make_array_cls(128), max(1, 120 // scale) * scale),
        ("arr512", make_array_cls(512), max(1, 30 // scale) * scale),
        ("wide64", make_wide_scalar_cls(64), max(1, 200 // scale) * scale),
    ]
    print("%-9s | %8s | %12s" % ("workload", "N", "solves/sec"))
    print("-" * 36)
    for name, cls, n in sweep:
        sps = _sps(t_cold(cls, n), n)
        print("%-9s | %8d | %12s" % (name, n, _fmt(sps)))
    print()

    # ---- B. phase attribution on a large workload ----
    print("## B. Phase attribution (arr128, cold)")
    n = max(1, 120 // scale) * scale
    total, buckets = phase_attribution(make_array_cls(128), n)
    print("do_randomize cumulative: %.3fs over %d solves\n" % (total, n))
    print("%-30s | %8s | %6s" % ("phase", "cum(s)", "%"))
    print("-" * 50)
    for label, ct in sorted(buckets.items(), key=lambda kv: -kv[1]):
        pct = (100.0 * ct / total) if total else 0.0
        print("%-30s | %8.3f | %5.1f%%" % (label, ct, pct))
    print()


if __name__ == "__main__":
    main()
