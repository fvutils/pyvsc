"""Schedule a suite's cells over pinned child processes (design §5.1).

Each (workload, arm, pattern) cell is one fresh child process: pyvsc keeps
global caches, and arms need different sys.paths. At most a quarter of the
physical cores run children at once, each pinned to its own physical core.
Cells are queued workload by workload and pattern by pattern with the arms
adjacent, so a load spike lands on every side of a ratio rather than on one.

The whole queue runs `rounds` times (default 2), and a cell's time is its
minimum over the rounds. A neighbour busy for a few seconds survives the
5-batch minimum inside one child, whose batches are back to back; it does
not survive a second measurement taken a minute later. Each round's value
is kept, so the spread is visible in the record.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import builds, calib, workloads
from .arms import ARMS


# Launched as a script, not with -m. Classic pyvsc calls inspect.stack() on
# every object construction, which costs O(frames x sys.modules) whenever a
# frame has no source file -- and `-m` puts frozen runpy frames on the stack.
# A script gives every cell the same shallow, fully-sourced stack. -P keeps
# the script's directory off sys.path, so perf's modules can't shadow anything.
CHILD = str(builds.HERE / "child.py")


def child_env(build: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(builds.pythonpath(build))
    env.pop("VSC_SOLVER", None)          # arms select their back-end explicitly
    env["PYTHONHASHSEED"] = "0"
    return env


def run_child(spec: dict, env: dict, timeout_s: float) -> dict:
    """Run one cell. Adds peak RSS and the child's own CPU from wait4."""
    with tempfile.TemporaryFile() as fout, tempfile.TemporaryFile() as ferr:
        p = subprocess.Popen([sys.executable, "-P", CHILD, json.dumps(spec)],
                             env=env, stdout=fout, stderr=ferr, cwd=str(builds.REPO))
        timer = threading.Timer(timeout_s, p.kill)
        timer.start()
        t0 = time.perf_counter()
        _, status, ru = os.wait4(p.pid, 0)
        p.returncode = 0                 # reaped here; stop Popen from waiting again
        timed_out = not timer.is_alive()
        timer.cancel()
        wall = time.perf_counter() - t0
        fout.seek(0)
        ferr.seek(0)
        lines = [l for l in fout.read().decode(errors="replace").splitlines() if l.strip()]
        err = ferr.read().decode(errors="replace")
    extra = {"maxrss_kb": ru.ru_maxrss, "proc_s": round(wall, 2)}
    if timed_out:
        return dict(extra, status="timeout")
    try:
        res = json.loads(lines[-1])
    except (IndexError, ValueError):
        code = os.waitstatus_to_exitcode(status)
        return dict(extra, status="error", error=f"child exit {code}, no result",
                    trace=err[-1500:])
    return dict(res, **extra)


def cells(spec: dict) -> list:
    out = []
    for w in spec["workloads"]:
        for pat in spec["patterns"]:
            for a in spec["arms"]:
                out.append((w, ARMS[a], pat))
    return out


def run_suite(spec: dict, workers: int = 0, log=None) -> list:
    reg = workloads.all_workloads()
    cores = calib.physical_cores()
    workers = workers or max(1, len(cores) // 4)
    free = queue.Queue()
    # cpu 0 takes most interrupts and housekeeping; start after it when we can
    for c in (cores[1:workers + 1] if len(cores) > workers else cores[:workers]):
        free.put(c)
    envs = {b: child_env(b) for b in {ARMS[a].build for a in spec["arms"]}}

    def one(cell):
        w, arm, pat = cell
        row = {"suite": spec["name"], "workload": w, "arm": arm.name, "pattern": pat}
        if getattr(reg[w], arm.frontend) is None:
            return dict(row, status="na", reason=f"no {arm.frontend} definition")
        child = {"workload": w, "frontend": arm.frontend, "backend": arm.backend,
                 "pattern": pat, "batch_s": spec.get("batch_s", 0.3),
                 "validate_only": spec.get("validate_only", False),
                 "draws": spec.get("draws", 20),
                 # an old build that can't define today's class is n/a, not broken
                 "na_on_define_error": arm.build != "head"}
        cpu = free.get()
        try:
            res = run_child(dict(child, cpu=cpu), envs[arm.build], spec.get("timeout_s", 60))
        finally:
            free.put(cpu)
        row.update(res)
        if log:
            log(row)
        return row

    todo = cells(spec)
    rounds = 1 if spec.get("validate_only") else spec.get("rounds", 2)
    with ThreadPoolExecutor(workers) as ex:
        results = [list(ex.map(one, todo)) for _ in range(rounds)]
    return [merge(rs) for rs in zip(*results)]


_WORST = ("invalid", "error", "timeout")


def merge(rs: tuple) -> dict:
    """One cell from its rounds: the worst failure if any, else the fastest round."""
    if len(rs) == 1:
        return rs[0]
    for st in _WORST:
        bad = [r for r in rs if r.get("status") == st]
        if bad:
            return dict(bad[0], rounds=len(rs))
    ok = [r for r in rs if r.get("status") == "ok"]
    if not ok:
        return dict(rs[0], rounds=len(rs))
    best = dict(min(ok, key=lambda r: r["cpu_us"]))
    best["rounds_us"] = [r["cpu_us"] for r in ok]
    best["validated"] = sum(r.get("validated", 0) for r in ok)
    best["maxrss_kb"] = max(r["maxrss_kb"] for r in ok)
    return best
