"""Machine fingerprint, host load and calibration kernels (design §5.4).

pyvsc is Python-bound, so the kernels are too: a fixed pure-Python workload
shaped like pyvsc's hot loops (attribute and dict traffic, small objects), and
a fixed Boolector solve loop. They run in a child of the head build, pinned,
min of 5. Their times say whether the machine and interpreter are the ones
earlier runs used; every trended number is a same-run ratio, so the kernels
detect drift rather than correct for it.

machine() is dv-solve's derivation exactly (tests/perf/calib.py), so a
machine has the same id in both repos' histories.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPS = 5


def _py_kernel():
    class Node:
        __slots__ = ("kind", "val", "kids")

        def __init__(self, kind, val, kids):
            self.kind, self.val, self.kids = kind, val, kids

    def build(d, i):
        if d == 0:
            return Node("leaf", i, ())
        return Node("op", i, (build(d - 1, 2 * i), build(d - 1, 2 * i + 1)))

    def walk(n, env):
        if n.kind == "leaf":
            return env.get(n.val & 63, n.val)
        a, b = walk(n.kids[0], env), walk(n.kids[1], env)
        return (a + b) & 0xFFFF if n.val & 1 else (a ^ b)

    tree = build(12, 1)
    acc = 0
    for r in range(400):
        env = {k: (k * 2654435761 + r) & 0xFFFF for k in range(64)}
        acc ^= walk(tree, env)
    return acc


def _btor_kernel():
    import pyboolector
    acc = 0
    for i in range(2000):
        b = pyboolector.Boolector()
        b.Set_opt(pyboolector.BtorOption.BTOR_OPT_MODEL_GEN, True)
        s8 = b.BitVecSort(8)
        x, y, z = b.Var(s8, "x"), b.Var(s8, "y"), b.Var(s8, "z")
        b.Assert(b.Ult(x, y))
        b.Assert(b.Ult(y, z))
        b.Assert(b.Eq(b.Add(x, z), b.Const(i & 0xFF, 8)) | b.Ugt(z, b.Const(200, 8)))
        if b.Sat() != b.SAT:
            raise RuntimeError("btor-kernel: unexpected UNSAT")
        acc ^= int(x.assignment, 2)
    return acc


KERNELS = {"py-kernel": _py_kernel, "btor-kernel": _btor_kernel}


def _child(cpu) -> dict:
    import time
    if cpu is not None:
        os.sched_setaffinity(0, {cpu})
    out = {}
    for name, fn in KERNELS.items():
        fn()                                    # warm
        best = None
        for _ in range(REPS):
            c0 = time.process_time()
            fn()
            dt = time.process_time() - c0
            best = dt if best is None else min(best, dt)
        out[name] = round(best * 1000, 1)
    return out


def calibrate(env: dict, cpu=None) -> dict:
    """Minimum CPU ms per kernel, measured in a child with env (the head build)."""
    r = subprocess.run([sys.executable, "-m", "perf.calib", json.dumps(cpu)],
                       env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"calibration failed:\n{r.stderr[-2000:]}")
    return {"kernel_cpu_ms": json.loads(r.stdout.strip().splitlines()[-1]), "reps": REPS}


def loadavg() -> float:
    """1-minute load average of the whole host (/proc/loadavg is not namespaced)."""
    try:
        return float(Path("/proc/loadavg").read_text().split()[0])
    except OSError:
        return -1.0


def machine() -> dict:
    """Machine class. Nothing here names the host."""
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem_gb = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                mem_gb = round(int(line.split()[1]) / (1024 * 1024))
                break
    except OSError:
        pass
    kernel = ".".join(platform.release().split(".")[:2])
    cores = os.cpu_count() or 0
    mid = hashlib.sha256(f"{cpu}|{cores}|{mem_gb}|{kernel}".encode()).hexdigest()[:5]
    return {"id": "m" + mid, "cpu": cpu, "cores": cores, "mem_gb": mem_gb, "kernel": kernel}


def physical_cores() -> list:
    """One logical CPU per physical core, among those this process may use."""
    seen, cores = set(), []
    for cpu in sorted(os.sched_getaffinity(0)):
        sib = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list")
        key = sib.read_text().strip() if sib.exists() else str(cpu)
        if key not in seen:
            seen.add(key)
            cores.append(cpu)
    return cores


if __name__ == "__main__":
    print(json.dumps(_child(json.loads(sys.argv[1]) if len(sys.argv) > 1 else None)))
