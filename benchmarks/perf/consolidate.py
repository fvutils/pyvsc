"""Turn run records into committed history (design §8.4).

    PYTHONPATH=benchmarks python3 -m perf.consolidate build/perf/runs/*.json.gz

Writes, under benchmarks/history/:
  <year>.jsonl              trend lines appended, kept sorted by utc, deduplicated
  releases/<tag>.json.gz    the full record of a release run (earliest valid wins)
  machines/<id>.json        a machine class the history has not seen before
  manifests/<hash>.json     a resolved suite (the order of a trend line's arrays)

Then checks everything it wrote for internal identifiers. It never commits:
review `git diff benchmarks/history`, render the pages, and commit the data
like code. Running it twice changes nothing.

Records come from local files for now (a run made by hand on the reference
machine). Reading them from the Forgejo `perf-*` artifacts arrives with
perf.yml (design phase F1).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

from . import schema
from .builds import REPO

HISTORY = REPO / "benchmarks" / "history"


def _internal_pattern():
    """The house identifier check, read from the docs workflow.

    The pattern names what it forbids, so it may only appear under
    .forgejo/workflows/ (the one path the check excludes); reading it from
    there keeps a single copy."""
    wf = (REPO / ".forgejo" / "workflows" / "docs.yml").read_text()
    m = re.search(r"pattern='([^']+)'", wf)
    if not m:
        raise RuntimeError("no identifier pattern in .forgejo/workflows/docs.yml")
    return re.compile(m.group(1))


def committed_lines(root: Path = HISTORY) -> list:
    out = []
    for p in sorted(root.glob("*.jsonl")):
        out += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out


def _write_jsonl(path: Path, lines: list) -> None:
    lines = sorted(lines, key=schema.line_key)
    path.write_text("".join(json.dumps(l, sort_keys=True, separators=(",", ":")) + "\n"
                            for l in lines))


def _write_once(path: Path, obj: dict) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")
    return True


def consolidate(records: list, root: Path = HISTORY) -> dict:
    """records: [(artifact name, run record)]. Returns a summary."""
    summary = {"runs": 0, "lines": 0, "invalid": 0, "noisy": 0, "dirty": 0, "releases": [],
               "machines": [], "manifests": [], "rejected": [], "written": []}
    by_year = {}
    for line in committed_lines(root):
        by_year.setdefault(line["utc"][:4], {})[schema.line_key(line)] = line
    for art, rec in records:
        errs = schema.validate(rec)
        if errs:
            summary["rejected"].append(f"{art}: {'; '.join(errs)}")
            continue
        summary["runs"] += 1
        summary["invalid"] += not rec["valid"]
        summary["noisy"] += rec["machine"]["noisy"]
        summary["dirty"] += rec["run"]["dirty"]
        for line in schema.trend_lines(rec, art):
            year = by_year.setdefault(line["utc"][:4], {})
            if schema.line_key(line) not in year:
                year[schema.line_key(line)] = line
                summary["lines"] += 1
        m = rec["machine"]
        mp = root / "machines" / f"{m['id']}.json"
        if _write_once(mp, {k: m[k] for k in ("id", "cpu", "cores", "mem_gb", "kernel")}):
            summary["machines"].append(m["id"])
            summary["written"].append(mp)
        for man in rec["manifests"].values():
            mp = root / "manifests" / f"{man['hash']}.json"
            if _write_once(mp, man):
                summary["manifests"].append(man["hash"])
                summary["written"].append(mp)
        ref = rec["run"]["ref"]
        if rec["kind"] == "release" and rec["valid"] and ref.startswith("refs/tags/"):
            tag = ref[len("refs/tags/"):]
            rp = root / "releases" / f"{tag}.json.gz"
            if not rp.exists():        # earliest valid one wins: records arrive oldest first
                rp.parent.mkdir(parents=True, exist_ok=True)
                with gzip.GzipFile(rp, "wb", mtime=0) as f:
                    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode())
                summary["releases"].append(tag)
                summary["written"].append(rp)
    for year, lines in by_year.items():
        if lines:
            p = root / f"{year}.jsonl"
            _write_jsonl(p, list(lines.values()))
            summary["written"].append(p)
    return summary


def internal_identifiers(paths: list) -> list:
    pat = _internal_pattern()
    hits = []
    for p in paths:
        data = gzip.decompress(p.read_bytes()).decode() if p.suffix == ".gz" else p.read_text()
        hits += [f"{p}: {m.group(0)}" for m in pat.finditer(data)]
    return hits


def load(path: Path) -> tuple:
    name = path.name[:-len(".json.gz")] if path.name.endswith(".json.gz") else path.stem
    return name, json.loads(gzip.decompress(path.read_bytes()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("records", nargs="+", help="run records (.json.gz) to consolidate")
    ap.add_argument("--history", default=str(HISTORY),
                    help="history directory (default benchmarks/history; another to preview)")
    a = ap.parse_args(argv)
    records = sorted((load(Path(p)) for p in a.records),
                     key=lambda r: r[1].get("run", {}).get("utc", ""))
    s = consolidate(records, Path(a.history))
    print(f"runs: {s['runs']}; trend lines added: {s['lines']}; invalid: {s['invalid']}; "
          f"noisy: {s['noisy']}; dirty: {s['dirty']}")
    for t in s["releases"]:
        print(f"release snapshot written: {t}")
    for m in s["machines"]:
        print(f"new machine class: {m}")
    for r in s["rejected"]:
        print(f"REJECTED {r}", file=sys.stderr)
    hits = internal_identifiers(s["written"])
    for h in hits:
        print(f"INTERNAL IDENTIFIER {h}", file=sys.stderr)
    if s["lines"] or s["releases"] or s["machines"]:
        print("review `git diff benchmarks/history`, render the pages, then commit")
    return 1 if s["rejected"] or hits else 0


if __name__ == "__main__":
    sys.exit(main())
