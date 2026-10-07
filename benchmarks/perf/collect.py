"""Run the perf suites and write one gzipped run record (design §8).

    PYTHONPATH=benchmarks python3 -m perf.collect --kind manual --suites core

Runs the smoke suite first (every workload, arm and pattern, 20 checked
draws; any failure stops the run before timing), then the calibration
kernels, then each suite. Writes build/perf/runs/<artifact-name>.json.gz
(--out to change) and prints the artifact name; with --github-output also
appends `name=<artifact-name>` to $GITHUB_OUTPUT.

A dirty src/ or dv-solve tree is refused unless --allow-dirty: numbers from
code that exists in no commit can't be reproduced, and such a record is
marked dirty. A record with a wrong answer anywhere is still written, with
`valid: false` and a reason, and the exit status is 1.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

from . import builds, calib, run, schema, suites
from .arms import ARMS

NOISY_LOAD = 4.0             # host 1-min load above this marks the run noisy
DEFAULT_OUT = builds.REPO / "build" / "perf" / "runs"


def harness_sha() -> str:
    h = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for p in sorted(here.rglob("*")):
        if p.suffix in (".py", ".json") and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(here)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


def _dvs_state(dv_file):
    """Version, commit and dirty flag of the dv-solve the head children loaded."""
    state = {"v": None, "commit": os.environ.get("DVS_COMMIT"), "dirty": False}
    if dv_file:
        root = Path(dv_file).resolve().parent
        t = builds.tree_state(root)
        if t["commit"]:
            state["commit"], state["dirty"] = t["commit"], t["dirty"]
    return state


def _provenance(cells: list) -> dict:
    out = {}
    for c in cells:
        v = c.get("versions")
        if not v:
            continue
        b = ARMS[c["arm"]].build
        d = out.setdefault(b, {})
        if "pyboolector" in v:
            d.setdefault("pyboolector", v["pyboolector"])
        if "constrainedrandom" in v:
            d.setdefault("constrainedrandom", v["constrainedrandom"])
        if v.get("dv_solve_file") and "dvs" not in d:
            d["dvs"] = dict(_dvs_state(v["dv_solve_file"]), v=v.get("dv_solve"))
        if "vsc_file" in v:
            d.setdefault("vsc_file", str(Path(v["vsc_file"]).resolve()
                                         .relative_to(builds.REPO)))
    return out


def _check_builds(prov: dict) -> list:
    """Each arm must have loaded the build it claims, not a stray site-packages copy."""
    errs = []
    for b, d in prov.items():
        if "vsc_file" not in d:
            continue
        want = "src/" if b == "head" else f"build/perf/builds/{b}/"
        if not d["vsc_file"].startswith(want):
            errs.append(f"build {b} loaded vsc from {d['vsc_file']}, expected {want}")
    return errs


def _log(row):
    st = row.get("status")
    val = f"{row['cpu_us']:.2f} us" if st == "ok" and "cpu_us" in row else st
    if st not in ("ok", "na"):
        val += f" {row.get('error') or row.get('bad') or ''}"
    print(f"  {row['suite']:<6} {row['workload']:<14} {row['pattern']:<5} "
          f"{row['arm']:<13} {val}", file=sys.stderr, flush=True)


def collect(kind: str, suite_names: list, a) -> dict:
    load0 = calib.loadavg()
    utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    src = builds.tree_state(builds.REPO, "src")
    run_number = os.environ.get("GITHUB_RUN_NUMBER")
    rec = {
        "schema": schema.SCHEMA, "valid": True, "kind": kind,
        "run": {"utc": utc, "commit": os.environ.get("GITHUB_SHA") or src["commit"],
                "ref": os.environ.get("GITHUB_REF", "local"), "dirty": src["dirty"],
                "harness_sha": harness_sha(),
                "workflow_run": int(run_number) if run_number else None},
        "python": platform.python_version(), "lock": builds.lock_sha(),
        "builds": {}, "calib": {}, "manifests": {}, "cells": [], "smoke": None,
    }
    specs = [suites.load(n) for n in suite_names]
    needed = {ARMS[x].build for s in specs for x in s["arms"]} - {"head"}
    try:
        for b in sorted(needed):
            builds.ensure(b)
        if not a.no_smoke:
            smoke = suites.load("smoke")
            print("smoke:", file=sys.stderr)
            rows = run.run_suite(smoke, a.workers, log=_log if a.verbose else None)
            bad = [f"{r['workload']}/{r['pattern']}/{r['arm']}: {r['status']} "
                   f"{r.get('error') or r.get('bad') or ''}".strip()
                   for r in rows if r["status"] not in ("ok", "na")]
            rec["smoke"] = {"cells": len(rows), "failed": bad}
            if bad:
                raise RuntimeError("smoke suite failed: " + "; ".join(bad[:5]))
        print("calibrating", file=sys.stderr)
        cores = calib.physical_cores()
        rec["calib"] = calib.calibrate(run.child_env("head"), cores[min(1, len(cores) - 1)])
        for spec in specs:
            print(f"suite {spec['name']}:", file=sys.stderr)
            rec["manifests"][spec["name"]] = spec["manifest"]
            rec["cells"] += run.run_suite(spec, a.workers, log=_log)
        rec["builds"] = _provenance(rec["cells"])
        for b in needed:
            rec["builds"].setdefault(b, {})["pins"] = builds.LOCK["builds"][b]
            if b == "stock":
                rec["builds"][b]["pyvsc"] = builds.LOCK["builds"][b][0].split("==")[1]
        errs = _check_builds(rec["builds"])
        if errs:
            raise RuntimeError("; ".join(errs))
        if rec["builds"].get("head", {}).get("dvs", {}).get("dirty") and not a.allow_dirty:
            raise RuntimeError("dv-solve tree is dirty (use --allow-dirty to record anyway)")
        invalid = [f"{c['suite']}/{c['workload']}/{c['pattern']}/{c['arm']}"
                   for c in rec["cells"] if c["status"] == "invalid"]
        if invalid:
            rec["valid"], rec["reason"] = False, "wrong answers: " + ", ".join(invalid)
    except RuntimeError as e:
        rec["valid"], rec["reason"] = False, str(e)
    load1 = calib.loadavg()
    # The 1-minute load at the end still counts our own children; discount them.
    workers = a.workers or max(1, len(calib.physical_cores()) // 4)
    rec["machine"] = dict(calib.machine(), loadavg_start=load0, loadavg_end=load1,
                          workers=workers, noisy=max(load0, load1 - workers) > NOISY_LOAD)
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=schema.KINDS, default="manual")
    ap.add_argument("--suites", default="core", help="comma-separated suite names")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--workers", type=int, default=0, help="0: a quarter of the physical cores")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--no-smoke", action="store_true", help="skip the smoke gate (debug only)")
    ap.add_argument("--verbose", action="store_true", help="log smoke cells too")
    ap.add_argument("--github-output", action="store_true")
    a = ap.parse_args(argv)
    names = [s for s in a.suites.split(",") if s]
    unknown = set(names) - set(suites.names())
    if unknown or "smoke" in names:
        ap.error(f"unknown or unrecordable suites: {', '.join(sorted(unknown | {'smoke'} & set(names)))}")
    if builds.tree_state(builds.REPO, "src")["dirty"] and not a.allow_dirty:
        print("src/ has uncommitted changes; commit them or pass --allow-dirty", file=sys.stderr)
        return 2

    rec = collect(a.kind, names, a)
    errs = schema.validate(rec)
    if errs:
        print("record fails its own schema:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    name = schema.artifact_name(a.kind, rec["run"]["utc"], rec["run"]["commit"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(out / f"{name}.json.gz", "wb", mtime=0) as f:
        f.write(json.dumps(rec, indent=1, sort_keys=True).encode())
    print(name)
    if a.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"name={name}\n")
    if not rec["valid"]:
        print(f"INVALID run: {rec['reason']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
