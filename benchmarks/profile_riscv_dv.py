"""Where one riscv-dv pygen program spends its time, by direct timers.

    PYTHONPATH=src:benchmarks python3 benchmarks/profile_riscv_dv.py \
        [--backend dv-solve|boolector|none] [--seed 1] [--instr-cnt N] [--no-gc]

Generates one program through benchmarks/perf/riscv_dv_child.py (same riscv-dv
checkout and fixes as the riscv-dv suite) with process-CPU timers around the
phases that matter, and reports seconds, ms per generated instruction and
share:

  * the instruction deep-copy (pygen's get_rand_instr copies a template);
  * randomize() and, inside it, the bound visitor, array expansion, RandSet
    partition and the back-end's solve_randset;
  * inside dv-solve's back-end, every native libdv_solve call, timed at the
    ctypes boundary (wall time, so it includes kernel time a user-mode
    `perf record` misses);
  * the garbage collector, per generation (gc.callbacks).

--no-gc disables the collector, which shows each phase's own cost: with it
on, a collection is charged to whichever phase happened to allocate. Timers
nest: a phase's time includes the phases and GC inside it. `--backend none`
runs the installed pyvsc without selecting a back-end (an old release).

For a sampled whole-stack view (pygen + pyvsc + dv-solve C):

    perf record -F 2000 -g -o out.data -- python3 -X perf benchmarks/profile_riscv_dv.py ...
    perf script -i out.data > out.txt
    python3 benchmarks/profile_fold.py out.txt --buckets
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import copy
import gc
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "perf"))

acc = collections.Counter()
calls = collections.Counter()
_depth = collections.Counter()


def _timed(label, f):
    def w(*a, **k):
        if _depth[label]:
            return f(*a, **k)
        _depth[label] += 1
        calls[label] += 1
        t = time.process_time()
        try:
            return f(*a, **k)
        finally:
            acc[label] += time.process_time() - t
            _depth[label] -= 1
    return w


def _wrap(owner, name, label):
    f = getattr(owner, name)
    w = _timed(label, f)
    setattr(owner, name, staticmethod(w) if isinstance(owner.__dict__.get(name), staticmethod) else w)


def _instrument_pyvsc():
    import vsc.model.randomizer as rz
    _wrap(rz.Randomizer, "do_randomize", "randomize()")
    _wrap(rz.Randomizer, "randomize", "randomize/solve loop")
    for mod, cls, meth, label in (
            ("vsc.visitors.variable_bound_visitor", "VariableBoundVisitor", "process", "randomize/variable bounds"),
            ("vsc.visitors.array_constraint_builder", "ArrayConstraintBuilder", "build", "randomize/array expansion"),
            ("vsc.model.rand_info_builder", "RandInfoBuilder", "build", "randomize/randset partition"),
            ("vsc.model.solver.dvsolve_backend", "DvSolveBackend", "solve_randset", "randomize/solve loop/back-end"),
            ("vsc.model.solver.boolector_backend", "BoolectorBackend", "solve_randset", "randomize/solve loop/back-end"),
            ("vsc.model.solver.dvsolve_backend", "DvSolveBackend", "_populate_builder", "randomize/solve loop/back-end/translate+build"),
    ):
        try:
            m = __import__(mod, fromlist=[cls])
            _wrap(getattr(m, cls), meth, label)
        except (ImportError, AttributeError):
            pass


_NATIVE = ("dvs_solver_compile", "dvs_solver_solve", "dvs_solver_get_value", "dvs_solver_reset",
           "dvs_solver_create", "dvs_block_alloc_create", "dvs_solver_destroy")


def _instrument_native():
    try:
        import dv_solve.ctx as ctx
    except ImportError:
        return
    lib = ctx._load_lib()
    if lib is None:
        return

    class W:
        def __init__(self, name, f):
            self.name, self.f = name, f

        def __call__(self, *a):
            t = time.perf_counter()
            try:
                return self.f(*a)
            finally:
                acc["native/" + self.name] += time.perf_counter() - t
                calls["native/" + self.name] += 1

        def __getattr__(self, k):
            return getattr(self.f, k)
    for n in _NATIVE:
        if hasattr(lib, n):
            setattr(lib, n, W(n, getattr(lib, n)))
    ctx._load_lib = lambda: lib


def _instrument_deepcopy():
    real = copy.deepcopy

    def deepcopy(x, memo=None, _nil=[]):
        if _depth["deepcopy"]:
            return real(x, memo)
        _depth["deepcopy"] += 1
        calls["instruction deepcopy"] += 1
        t = time.process_time()
        try:
            return real(x, memo)
        finally:
            acc["instruction deepcopy"] += time.process_time() - t
            _depth["deepcopy"] -= 1
    copy.deepcopy = deepcopy


def _instrument_gc():
    t0 = [0.0]

    def cb(phase, info):
        if phase == "start":
            t0[0] = time.process_time()
        else:
            g = f"gc/gen{info['generation']}"
            acc[g] += time.process_time() - t0[0]
            calls[g] += 1
    gc.callbacks.append(cb)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backend", default="dv-solve")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--instr-cnt", type=int, default=None)
    ap.add_argument("--test", default="riscv_arithmetic_basic_test")
    ap.add_argument("--no-gc", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from perf import riscv_dv
    import riscv_dv_child as child
    spec = {"rdv": str(riscv_dv.ensure()), "test": a.test, "seed": a.seed,
            "backend": None if a.backend == "none" else a.backend}
    if a.instr_cnt:
        spec["instr_cnt"] = a.instr_cnt

    if a.no_gc:
        gc.disable()
    _instrument_gc()
    _instrument_deepcopy()
    _instrument_pyvsc()
    _instrument_native()
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res = child.measure(spec)
    if res.get("status") != "ok":
        print(json.dumps(res), file=sys.stderr)
        return 1

    cpu, n = res["cpu_s"], res["instrs"]
    gc_s = sum(v for k, v in acc.items() if k.startswith("gc/"))
    rows = sorted(acc.items())
    if a.json:
        print(json.dumps({"backend": a.backend, "seed": a.seed, "gc": not a.no_gc, "cpu_s": cpu,
                          "instrs": n, "randomize_calls": res["randomize_calls"],
                          "phases_s": {k: round(v, 3) for k, v in rows},
                          "calls": dict(calls)}))
        return 0
    print(f"{a.test} seed {a.seed}, back-end {a.backend}, GC {'off' if a.no_gc else 'on'}: "
          f"{cpu:.2f} s CPU, {n} instructions ({cpu / n * 1e3:.2f} ms each), "
          f"{res['randomize_calls']} randomize() calls, GC {gc_s:.2f} s")
    print(f"  {'phase':52s} {'s':>8s} {'ms/instr':>9s} {'share':>6s} {'calls':>8s}")
    for k, v in rows:
        print(f"  {k:52s} {v:8.2f} {v / n * 1e3:9.3f} {100 * v / cpu:5.1f}% {calls[k]:8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
