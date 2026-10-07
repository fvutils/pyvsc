"""Run records and trend lines (design §8.1, §8.2).

A run record is the full result of one collect: every cell, with batches,
latency percentiles and peak RSS. A trend line is the compact committed
summary of a run: per suite, the CPU µs per call of every (workload,
pattern, arm) cell, in manifest order, so any ratio stays recomputable.
Validation is hand-written so nothing beyond the standard library is needed.
"""
from __future__ import annotations

import re

SCHEMA = 1          # run record
TREND = 1           # trend line ("h")
KINDS = ("nightly", "release", "ladder", "manual", "backfill")
ARTIFACT_RE = re.compile(r"^perf-(?P<kind>[a-z]+)-(?P<utc>\d{8}T\d{6}Z)-(?P<sha>[0-9a-f]{7,40})$")

_REQUIRED = {"schema": int, "valid": bool, "kind": str, "run": dict, "machine": dict,
             "builds": dict, "calib": dict, "manifests": dict, "cells": list, "python": str}
_RUN = {"utc": str, "commit": str, "ref": str, "dirty": bool}
_MACHINE = {"id": str, "cpu": str, "cores": int, "mem_gb": int, "kernel": str,
            "loadavg_start": float, "loadavg_end": float, "noisy": bool}
FAIL_STATES = ("timeout", "invalid", "error")


def artifact_name(kind: str, utc: str, commit: str) -> str:
    return f"perf-{kind}-{utc}-{commit[:7]}"


def validate(rec: dict) -> list:
    """Problems with a run record; empty when it is well formed."""
    errs = []

    def need(obj, spec, where):
        for k, t in spec.items():
            if k not in obj:
                errs.append(f"{where}.{k} missing")
            elif t is float and isinstance(obj[k], (int, float)) and not isinstance(obj[k], bool):
                continue
            elif not isinstance(obj[k], t):
                errs.append(f"{where}.{k} is {type(obj[k]).__name__}, want {t.__name__}")

    if not isinstance(rec, dict):
        return ["record is not an object"]
    need(rec, _REQUIRED, "record")
    if errs:
        return errs
    if rec["schema"] != SCHEMA:
        errs.append(f"unknown schema {rec['schema']}")
    if rec["kind"] not in KINDS:
        errs.append(f"unknown kind {rec['kind']!r}")
    need(rec["run"], _RUN, "run")
    need(rec["machine"], _MACHINE, "machine")
    if not re.fullmatch(r"\d{8}T\d{6}Z", rec["run"].get("utc", "")):
        errs.append("run.utc not in YYYYMMDDTHHMMSSZ form")
    if not rec["valid"] and not rec.get("reason"):
        errs.append("invalid record without a reason")
    for i, c in enumerate(rec["cells"]):
        for k in ("suite", "workload", "arm", "pattern", "status"):
            if k not in c:
                errs.append(f"cells[{i}].{k} missing")
        if c.get("status") == "ok" and not isinstance(c.get("cpu_us"), (int, float)):
            errs.append(f"cells[{i}] ok without cpu_us")
    return errs


def _us(x):
    return None if x is None else (round(x, 2) if x < 1000 else round(x, 1))


def trend_lines(rec: dict, artifact: str) -> list:
    """One line per run: the head build, with stock and cr as arms beside it."""
    head = rec["builds"].get("head", {})
    line = {
        "h": TREND, "utc": rec["run"]["utc"], "commit": rec["run"]["commit"],
        "dirty": rec["run"]["dirty"], "ref": rec["run"]["ref"], "kind": rec["kind"],
        "build": "head", "valid": rec["valid"], "noisy": rec["machine"]["noisy"],
        "machine": rec["machine"]["id"], "py": ".".join(rec["python"].split(".")[:2]),
        "dvs": head.get("dvs"), "btor": head.get("pyboolector"),
        "stock": rec["builds"].get("stock", {}).get("pyvsc"),
        "cr": rec["builds"].get("cr", {}).get("constrainedrandom"),
        "lock": rec.get("lock"), "harness": rec["run"].get("harness_sha"),
        "calib": rec["calib"].get("kernel_cpu_ms", {}), "artifact": artifact,
    }
    if rec.get("measured_later"):
        line["measured_later"] = True
    if not rec["valid"]:
        line["reason"] = rec.get("reason", "")
    perf = {}
    fail = {s: [] for s in FAIL_STATES}
    for name, man in rec["manifests"].items():
        by = {(c["workload"], c["pattern"], c["arm"]): c
              for c in rec["cells"] if c["suite"] == name}
        if not by:
            continue
        w = {}
        for wl in man["workloads"]:
            rows = []
            for pat in man["patterns"]:
                row = []
                for arm in man["arms"]:
                    c = by.get((wl["name"], pat, arm), {})
                    st = c.get("status")
                    row.append(_us(c.get("cpu_us")) if st == "ok" else None)
                    if st in fail:
                        fail[st].append(f"{name}/{wl['name']}/{pat}/{arm}")
                rows.append(row)
            w[wl["name"]] = rows
        perf[name] = {"m": man["hash"], "arms": man["arms"], "pat": man["patterns"], "w": w}
    line["perf"] = perf
    line["fail"] = fail
    return [line]


def line_key(line: dict) -> tuple:
    return (line["utc"], line["commit"], line["kind"], line["build"])
