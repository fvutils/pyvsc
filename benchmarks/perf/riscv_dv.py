"""The riscv-dv suite: generate riscv-dv programs with pygen on each arm.

riscv-dv (github.com/chipsalliance/riscv-dv, formerly google/riscv-dv) is a
RISC-V instruction-stream generator written in SystemVerilog/UVM; `pygen` is
its Python port, built on pyvsc. It's the one benchmark here that is someone
else's real program, and the one most public criticism of pyvsc's speed
refers to. riscv-dv's own CI runs pygen on exactly one test,
`riscv_arithmetic_basic_test` (seed 999), and the other testlist entries don't
complete on pygen with any pyvsc (unported features such as callstack_gen),
so that test is the workload.

A suite manifest names testlist entries, seeds and arms:

    {"app": "riscv-dv", "tests": [{"name": "arith_basic",
     "test": "riscv_arithmetic_basic_test"}], "seeds": [999, 1, 2, 3, 4],
     "arms": [...], "timeout_s": 900}

Each (test, seed, arm) is one fresh child process (riscv_dv_child.py). A
cell is (test, "program", arm) and its number is CPU µs per generated
instruction, pooled over the seeds: total CPU / total instructions. Pooling
matters because pygen draws the main program's length uniformly from
[10, instr_cnt] (riscv-dv's SV sum constraint was never ported), so program
length differs per seed and per arm. instructions/s = 1e6 / that number.

riscv-dv is pinned in tools.lock.json and checked out under
build/perf/builds/riscv-dv-<sha>; the packages/riscv-dv clone is used as the
git source when it has the commit, so no network is needed in a workspace.

The dc arms run the port instead: pygen rewritten for the dataclass
front-end, in the packages/riscv-dv-new working tree (branch pyvsc-dc,
doc/notes/riscv_dv_vdc_port_plan.md). So for this app F = classic-dvs /
dc-dvs is what the port buys, on the same back-end. The port tree is not
pinned, so a suite with a dc arm is for development and can't be recorded.
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import builds, calib, run
from .arms import ARMS

CHILD = str(builds.HERE / "riscv_dv_child.py")
PATTERN = "program"
URL = "https://github.com/chipsalliance/riscv-dv.git"


def pin() -> str:
    return builds.LOCK["riscv-dv"]["commit"]


def ensure() -> Path:
    """A checkout of the pinned riscv-dv commit."""
    commit = pin()
    target = builds.ROOT / f"riscv-dv-{commit[:12]}"
    if (target / ".git").exists() and builds.tree_state(target)["commit"] == commit:
        return target
    local = builds.REPO / "packages" / "riscv-dv"
    src = URL
    if (local / ".git").exists():
        r = subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=local,
                           capture_output=True)
        if r.returncode == 0:
            src = str(local)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        r = subprocess.run(["git", "clone", "-q", "--no-checkout", src, str(target)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"riscv-dv clone from {src} failed:\n{r.stderr[-1500:]}")
    r = subprocess.run(["git", "-c", "advice.detachedHead=false", "checkout", "-q", commit],
                       cwd=target, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"riscv-dv checkout of {commit} failed:\n{r.stderr[-1500:]}")
    return target


PORT = builds.REPO / "packages" / "riscv-dv-new"


def port_tree() -> Path:
    if not (PORT / "pygen").is_dir():
        raise RuntimeError(f"the port tree {PORT} is missing")
    return PORT


def uses_port(spec: dict) -> bool:
    return any(ARMS[a].frontend == "dc" for a in spec["arms"])


def _tree(arm, rdv: Path) -> tuple:
    """(checkout, apply the import-time riscv-dv fixes) for an arm."""
    if arm.frontend == "dc":
        return port_tree(), False
    return rdv, True


def _jobs(spec: dict, rdv: Path, validate: bool) -> list:
    seeds = spec["validate_seeds"] if validate else spec["seeds"]
    out = []
    for t in spec["tests"]:
        for seed in seeds:
            for a in spec["arms"]:
                arm = ARMS[a]
                tree, fixes = _tree(arm, rdv)
                child = {"rdv": str(tree), "fixes": fixes, "test": t["test"], "seed": seed,
                         "backend": arm.backend, "target": t.get("target", "rv32imc")}
                ic = spec.get("validate_instr_cnt") if validate else t.get("instr_cnt")
                if ic:
                    child["instr_cnt"] = ic
                out.append((t["name"], seed, arm, child))
    return out


def _validate_env(env: dict, arm) -> dict:
    """The validation pass runs dv-solve with its own model check and the
    Boolector cross-check on, so a wrong answer is loud."""
    if arm.backend == "dv-solve":
        env = dict(env, VSC_DVSOLVE_VALIDATE="1", VSC_DVSOLVE_XCHECK="1")
    return env


def run_suite(spec: dict, workers: int = 0, log=None) -> list:
    rdv = ensure()
    cores = calib.physical_cores()
    workers = workers or max(1, len(cores) // 4)
    free = queue.Queue()
    for c in (cores[1:workers + 1] if len(cores) > workers else cores[:workers]):
        free.put(c)
    envs = {b: run.child_env(b) for b in {ARMS[a].build for a in spec["arms"]}}
    timeout = spec.get("timeout_s", 900)

    def one(job, validate):
        name, seed, arm, child = job
        env = envs[arm.build]
        if validate:
            env = _validate_env(env, arm)
        cpu = free.get()
        try:
            res = run.run_child(dict(child, cpu=cpu), env, timeout, script=CHILD)
        finally:
            free.put(cpu)
        res.update(test=name, seed=seed, arm=arm.name, validate=validate)
        if log:
            log(res)
        return res

    with ThreadPoolExecutor(workers) as ex:
        checks = list(ex.map(lambda j: one(j, True), _jobs(spec, rdv, True)))
        rounds = [list(ex.map(lambda j: one(j, False), _jobs(spec, rdv, False)))
                  for _ in range(spec.get("rounds", 2))]
    return cells(spec, checks, [merge(rs) for rs in zip(*rounds)])


def merge(rs: tuple) -> dict:
    """One (seed, arm) run from its rounds: a failure if any round failed, else
    the round with the least CPU. Generation is seed-deterministic, so every
    round must have written the same program; a difference is an error."""
    bad = [r for r in rs if r.get("status") != "ok"]
    if bad:
        return dict(bad[0], rounds=len(rs))
    shas = {r["asm_sha"] for r in rs}
    if len(shas) > 1:
        return dict(rs[0], status="error", rounds=len(rs),
                    error=f"rounds generated different programs: {sorted(shas)}")
    best = dict(min(rs, key=lambda r: r["cpu_s"]))
    best["rounds_cpu_s"] = [r["cpu_s"] for r in rs]
    return best


def cells(spec: dict, checks: list, runs: list) -> list:
    """Per (test, arm): pooled µs per instruction, with the per-seed runs kept.

    A head-build arm with any oracle violation, dv-solve validation failure or
    error is invalid. A side-installed release is measured as it is: its
    violations are recorded (`violations`) but don't invalidate it, since
    that's the behaviour its users get."""
    out = []
    for t in spec["tests"]:
        for a in spec["arms"]:
            arm = ARMS[a]
            mine = [r for r in runs if r["test"] == t["name"] and r["arm"] == a]
            vals = [r for r in checks if r["test"] == t["name"] and r["arm"] == a]
            cell = {"suite": spec["name"], "workload": t["name"], "arm": a,
                    "pattern": PATTERN, "seeds": mine, "validation": vals}
            bad = [r for r in mine + vals if r.get("status") != "ok"]
            ok = [r for r in mine + vals if r.get("status") == "ok"]
            viol = sum(r.get("violations", 0) + r.get("corrupt_size", 0) for r in ok)
            cell["violations"] = viol
            kinds = {"corrupt_size": sum(r.get("corrupt_size", 0) for r in ok)}
            for r in ok:
                for k, v in (r.get("violations_by") or {"gpr": r.get("violations", 0)}).items():
                    kinds[k] = kinds.get(k, 0) + v
            cell["violation_kinds"] = kinds
            cell["versions"] = next((r["versions"] for r in mine if r.get("versions")), None)
            if bad:
                st = "timeout" if any(r.get("status") == "timeout" for r in bad) else "error"
                cell.update(status=st, error="; ".join(
                    f"seed {r['seed']}{' (validation)' if r['validate'] else ''}: "
                    f"{r.get('status')} {r.get('error', '')}".strip() for r in bad)[:2000])
            elif viol and arm.build == "head":
                cell.update(status="invalid", bad=next(
                    (r.get("first_violation") for r in ok if r.get("violations")),
                    "avail_regs size differs from its element count"))
            else:
                cpu = sum(r["cpu_s"] for r in mine)
                n = sum(r["instrs"] for r in mine)
                calls = sum(r["randomize_calls"] for r in mine)
                cell.update(status="ok", cpu_us=round(cpu / n * 1e6, 1), instrs=n,
                            cpu_s=round(cpu, 3), randomize_calls=calls,
                            us_per_call=round(cpu / calls * 1e6, 1) if calls else None,
                            maxrss_kb=max(r.get("maxrss_kb", 0) for r in mine))
                fb = {}
                for r in mine:
                    for k, v in (r.get("fallback") or {}).items():
                        fb[k] = fb.get(k, 0) + v
                if fb:
                    cell["fallback"] = fb
            out.append(cell)
    return out


def manifest(spec: dict) -> dict:
    """The resolved suite. The harness files' hash stands in for a workload's
    source hash: the child and its riscv-dv fixes are what define the program."""
    import hashlib
    h = hashlib.sha256()
    for p in (CHILD, __file__):
        h.update(Path(p).read_bytes())
    sha = h.hexdigest()[:16]
    man = {
        "suite": spec["name"], "app": "riscv-dv", "riscv_dv": pin(),
        "workloads": [{"name": t["name"], "family": "app", "rev": t.get("rev", 1), "sha": sha,
                       "test": t["test"], "instr_cnt": t.get("instr_cnt"),
                       "target": t.get("target", "rv32imc"),
                       "frontends": sorted({ARMS[a].frontend for a in spec["arms"]})}
                      for t in spec["tests"]],
        "arms": list(spec["arms"]), "patterns": [PATTERN], "seeds": list(spec["seeds"]),
        "family_weights": {},
        "protocol": {"timeout_s": spec.get("timeout_s", 900), "rounds": spec.get("rounds", 2),
                     "validate_seeds": list(spec["validate_seeds"]),
                     "validate_instr_cnt": spec.get("validate_instr_cnt"),
                     "metric": "cpu_us per generated instruction, pooled over seeds"},
    }
    if uses_port(spec):
        man["riscv_dv_port"] = builds.tree_state(PORT)
    man["hash"] = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()[:12]
    return man


def main(argv=None) -> int:
    """Quick look at one test on each arm, without recording anything:

        PYTHONPATH=benchmarks python3 -m perf.riscv_dv [--seeds 999] [--instr-cnt N]
    """
    import argparse
    from . import suites
    ap = argparse.ArgumentParser(description=main.__doc__.splitlines()[0])
    ap.add_argument("--suite", default="riscv-dv")
    ap.add_argument("--seeds", default=None, help="comma-separated; default the suite's")
    ap.add_argument("--instr-cnt", type=int, default=None)
    ap.add_argument("--workers", type=int, default=0)
    a = ap.parse_args(argv)
    spec = suites.load(a.suite)
    if a.seeds:
        spec["seeds"] = [int(s) for s in a.seeds.split(",")]
    if a.instr_cnt:
        for t in spec["tests"]:
            t["instr_cnt"] = a.instr_cnt
    for b in {ARMS[x].build for x in spec["arms"]} - {"head"}:
        builds.ensure(b)

    def log(r):
        v = (f"{r['cpu_s']:8.2f} s {r['instrs']:6d} instrs {r['violations']} viol"
             if r.get("status") == "ok" else f"{r.get('status')} {r.get('error', '')}")
        print(f"  {r['test']} seed {r['seed']:<5} {r['arm']:<13} "
              f"{'validate ' if r['validate'] else ''}{v}", file=sys.stderr, flush=True)
    for c in run_suite(spec, a.workers, log):
        print(json.dumps({k: c.get(k) for k in ("workload", "arm", "status", "cpu_us", "instrs",
                                                "randomize_calls", "us_per_call", "violations",
                                                "fallback", "error", "bad")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
