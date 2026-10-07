"""One measured cell, in its own process (design §5.1, §5.2).

    python3 -P benchmarks/perf/child.py '<json spec>'      (perf.run does this)

The spec names a workload, an arm's front-end and back-end, a pattern and a
CPU to pin to. The child builds the workload's class against whichever pyvsc
its PYTHONPATH holds, then:

  1. warms up (20 calls, untimed);
  2. validates: up to 300 draws, each checked by the workload's oracle;
     one failure makes the cell invalid;
  3. sizes a batch to take at least `batch_s` of CPU (20 to 200 000 calls);
  4. times 5 batches, gc.collect() before each, GC left on as users run it;
  5. times one more batch call by call for p50 / p95 / p99 latency;
  6. re-validates 100 draws, so state built up while timing can't hide a
     wrong answer.

Prints one JSON object on stdout. The primary number is CPU µs per call,
the minimum over the 5 batches.
"""
from __future__ import annotations

import gc
import json
import os
import random
import sys
import time
import traceback

WARMUP = 20
VALIDATE = 300
VALIDATE_S = 15.0         # validation stops early after this, if >= MIN_VALID drew
MIN_VALID = 20
BATCHES = 5
FLOOR, CAP = 20, 200_000


def _value(v):
    if isinstance(v, (int, bool)):
        return int(v)
    if isinstance(v, (list, tuple)) or (hasattr(v, "__iter__") and not isinstance(v, (str, bytes))):
        return [int(x) for x in v]
    return int(v)


def sample(obj, fields) -> dict:
    out = {}
    for f in fields:
        v = obj
        for part in f.split("."):
            v = getattr(v, part)
        out[f] = _value(v)
    return out


def build(w, frontend: str, backend):
    """→ (class, versions). Raises LookupError when the build can't express it."""
    versions = {}
    if frontend == "cr":
        import constrainedrandom as cr
        from importlib.metadata import version
        versions["constrainedrandom"] = version("constrainedrandom")
        return w.cr(cr), versions
    import vsc
    versions["vsc_file"] = vsc.__file__
    try:
        from importlib.metadata import version
        versions["pyboolector"] = version("pyboolector")
    except Exception:
        versions["pyboolector"] = None
    if backend is not None:
        if not hasattr(vsc, "set_solver_backend"):
            raise LookupError("this pyvsc has no back-end selection")
        vsc.set_solver_backend(backend)
        if backend == "dv-solve":
            try:
                import dv_solve
                versions["dv_solve"] = getattr(dv_solve, "__version__", None)
                versions["dv_solve_file"] = dv_solve.__file__
            except Exception:
                versions["dv_solve"] = None
    if frontend == "classic":
        return w.classic(vsc), versions
    try:
        import vsc.dc as vdc
    except ImportError as e:
        raise LookupError(f"this pyvsc has no dataclass front-end: {e}")
    return w.dc(vdc), versions


def _ops(cls, pattern):
    """→ (op, draw): op() is the timed call; draw() returns a fresh sample source."""
    if pattern == "cold":
        def op():
            cls().randomize()

        def draw():
            o = cls()
            o.randomize()
            return o
        return op, draw
    if pattern == "warm":
        obj = cls()
        op = obj.randomize

        def draw():
            obj.randomize()
            return obj
        return op, draw
    if pattern == "construct":
        return cls, None
    raise ValueError(f"unknown pattern {pattern!r}")


def _validate(draw, w, n, budget_s):
    t0 = time.perf_counter()
    done = 0
    for _ in range(n):
        s = sample(draw(), w.fields)
        if not w.check(s):
            return done, s
        done += 1
        if done >= MIN_VALID and time.perf_counter() - t0 > budget_s:
            break
    return done, None


def _batch(op, n):
    gc.collect()
    c0, w0 = time.process_time(), time.perf_counter()
    for _ in range(n):
        op()
    return time.process_time() - c0, time.perf_counter() - w0


def measure(spec: dict) -> dict:
    from perf import workloads
    w = workloads.get(spec["workload"])
    out = {"status": "ok"}
    random.seed(spec.get("seed", 0))
    try:
        cls, out["versions"] = build(w, spec["frontend"], spec.get("backend"))
    except LookupError as e:
        return {"status": "na", "reason": str(e)}
    except Exception as e:
        if not spec.get("na_on_define_error"):
            raise
        return {"status": "na", "reason": f"class does not define: {type(e).__name__}: {e}"}
    if cls is None:
        return {"status": "na", "reason": "no class for this front-end"}
    op, draw = _ops(cls, spec["pattern"])

    for _ in range(WARMUP):
        op()
    if spec.get("validate_only"):
        n, bad = _validate(draw, w, spec.get("draws", MIN_VALID), 1e9)
        out.update(validated=n)
        if bad is not None:
            out.update(status="invalid", bad=bad)
        return out
    if draw is not None:
        n, bad = _validate(draw, w, VALIDATE, VALIDATE_S)
        out["validated"] = n
        if bad is not None:
            out.update(status="invalid", bad=bad)
            return out

    batch_s = spec.get("batch_s", 0.3)
    n = FLOOR
    cpu, _ = _batch(op, n)
    while cpu < batch_s and n < CAP:
        n = min(CAP, max(n * 2, int(n * batch_s * 1.2 / max(cpu, 1e-6))))
        cpu, _ = _batch(op, n)
    batches = [_batch(op, n) for _ in range(BATCHES)]
    cpus = [c / n * 1e6 for c, _ in batches]
    walls = [wl / n * 1e6 for _, wl in batches]
    out.update(n=n, cpu_us=round(min(cpus), 3), wall_us=round(min(walls), 3),
               cpu_batches_us=[round(c, 3) for c in cpus])

    lat = []
    ln = min(n, 20_000)
    gc.collect()
    for _ in range(ln):
        t0 = time.perf_counter_ns()
        op()
        lat.append(time.perf_counter_ns() - t0)
    lat.sort()
    out["lat_us"] = {p: round(lat[min(ln - 1, int(ln * q))] / 1000, 3)
                     for p, q in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))}

    if draw is not None:
        n2, bad = _validate(draw, w, 100, 1e9)
        out["validated"] += n2
        if bad is not None:
            out.update(status="invalid", bad=bad, when="after timing")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    spec = json.loads(argv[0])
    if spec.get("cpu") is not None:
        os.sched_setaffinity(0, {spec["cpu"]})
    try:
        res = measure(spec)
    except Exception as e:
        res = {"status": "error", "error": f"{type(e).__name__}: {e}",
               "trace": traceback.format_exc()[-1500:]}
    sys.stdout.write("\n" + json.dumps(res) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
