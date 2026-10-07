"""Render the results pages from the committed history (design §8.4).

    PYTHONPATH=benchmarks python3 -m perf.render --out doc/source/results

Writes reStructuredText into the Sphinx tree, where docs.yml builds it into
the doc set published at dvkit.org/fvutils/pyvsc/results/. The pages are a
function of benchmarks/history/ and are never committed (only the
hand-written methodology.rst beside them is). Standard library only, and
Python 3.10, so it runs on the Forgejo runner's stock interpreter.

The "current" run is the newest valid trend line that was not measured on a
dirty tree; the run-history table lists every line, bad ones included.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import normalize, svg
from .arms import HEADLINE
from .consolidate import HISTORY, committed_lines

SUITE = "core"
RATIO_TEXT = {
    "T": "whole stack: classic + Boolector → dataclass + dv-solve",
    "B": "back-end: Boolector → dv-solve, classic front-end",
    "F": "front-end: classic → dataclass, on dv-solve",
    "S": "today's dataclass + dv-solve vs pyvsc 0.9.5 as installed",
    "S0": "today's classic + Boolector vs pyvsc 0.9.5 (a user who changes nothing)",
}
PATTERN_TEXT = {
    "cold": "construct a fresh object and randomize it once (the create-many pattern: "
            "sequence items, generators)",
    "warm": "randomize the same object repeatedly",
}


def _fmt_us(v):
    if v is None:
        return "n/a"
    return f"{v:,.0f}" if v >= 100 else f"{v:.1f}"


def _fmt_x(v):
    if v is None:
        return "–"
    return f"{v:.0f}×" if v >= 100 else (f"{v:.1f}×" if v >= 10 else f"{v:.2f}×")


def _date(utc: str) -> str:
    return f"{utc[0:4]}-{utc[4:6]}-{utc[6:8]} {utc[9:11]}:{utc[11:13]} UTC"


def _table(header: list, rows: list, widths=None) -> list:
    out = [".. list-table::", "   :header-rows: 1"]
    if widths:
        out.append("   :widths: " + " ".join(str(w) for w in widths))
    out.append("")
    for r in [header] + rows:
        out.append("   * - " + str(r[0]))
        out += [f"     - {c}" for c in r[1:]]
    out.append("")
    return out


def _manifest(line: dict, root: Path) -> dict:
    h = line["perf"][SUITE]["m"]
    p = root / "manifests" / f"{h}.json"
    if not p.exists():
        raise RuntimeError(f"history has no manifest {h} for the line at {line['utc']}")
    return json.loads(p.read_text())


def current(lines: list):
    good = [l for l in lines if l["valid"] and not l.get("dirty") and SUITE in l.get("perf", {})]
    return good[-1] if good else None


def _short(c):
    return (c or "")[:7]


def index_page(lines: list, root: Path) -> str:
    cur = current(lines)
    out = ["Performance results", "===================", "",
           "How fast pyvsc randomizes, measured on every recorded run and kept as a committed",
           "history in the repository (``benchmarks/history/``). Each number is CPU time per",
           "``randomize()`` call; every ratio compares two arms measured in the same run on the",
           "same machine. :doc:`methodology` says how, and how to reproduce one number.", ""]
    if cur is None:
        out += ["No valid run has been recorded yet.", ""]
        return "\n".join(out)
    man = _manifest(cur, root)
    machine = {}
    mp = root / "machines" / f"{cur['machine']}.json"
    if mp.exists():
        machine = json.loads(mp.read_text())
    dvs = cur.get("dvs") or {}
    out += ["Latest run", "----------", ""]
    prov = [
        ("Measured", _date(cur["utc"]) + (" (host was busy: treat small differences as noise)"
                                          if cur.get("noisy") else "")),
        ("pyvsc", f"``{_short(cur['commit'])}`` ({cur.get('ref', 'local')}, {cur['kind']} run)"),
        ("dv-solve", f"{dvs.get('v') or '?'} (``{_short(dvs.get('commit'))}``)"),
        ("pyboolector", cur.get("btor") or "?"),
        ("Anchor", f"pyvsc {cur.get('stock') or '?'} from PyPI"),
        ("constrainedrandom", cur.get("cr") or "not measured"),
        ("Python", cur["py"]),
        ("Machine", f"``{cur['machine']}``: {machine.get('cpu', '?')}, "
                    f"{machine.get('cores', '?')} threads"),
    ]
    out += _table(["", ""], [[k, v] for k, v in prov], widths=[1, 4])
    fails = sum(len(v) for v in cur.get("fail", {}).values())
    out += ["Every measured cell first had at least 300 samples checked against an independent",
            "Python oracle for the workload's constraints, before and after timing. "
            + ("No cell produced a wrong answer, an error or a timeout."
               if not fails else f"{fails} cell(s) failed; they are excluded from every ratio:"
               f" {', '.join(sum(cur['fail'].values(), []))}."), ""]

    out += ["Headline", "--------", "",
            "Geometric mean over the suite's workloads, each family weighted equally.",
            "Above 1× means the second configuration is faster.", ""]
    rows = []
    for name in HEADLINE:
        rows.append([RATIO_TEXT[name]] + [_fmt_x(normalize.score(cur, SUITE, man, p, name))
                                          for p in man["patterns"]])
    out += _table(["Speed-up"] + [p for p in man["patterns"]], rows, widths=[5, 1, 1])
    out += ["Patterns: " + "; ".join(f"**{p}**: {PATTERN_TEXT.get(p, p)}"
                                     for p in man["patterns"]) + ".", ""]

    c = normalize.cells(cur, SUITE)
    arms = man["arms"]
    for pat in man["patterns"]:
        title = f"Per workload: {pat}"
        out += [title, "-" * len(title), "", f"CPU µs per call ({PATTERN_TEXT.get(pat, pat)}).", ""]
        rows = []
        for w in man["workloads"]:
            n = w["name"]
            rows.append([f"``{n}``"] + [_fmt_us(c.get((n, pat, a))) for a in arms]
                        + [_fmt_x(normalize.ratio(c, n, pat, r)) for r in ("T", "B", "F")])
        out += _table(["workload"] + [f"``{a}``" for a in arms] + ["T", "B", "F"], rows)
    out += ["Arms: ``classic`` is the ``@vsc.randobj`` front-end, ``dc`` the dataclass front-end;",
            "``btor`` is Boolector, ``dvs`` dv-solve. ``stock`` is pyvsc 0.9.5 from PyPI, the fixed",
            "anchor. ``cr`` is `constrainedrandom <https://github.com/imc-trading/constrainedrandom>`_,",
            "an external reference shown where it can express the workload, and never part of a",
            "pyvsc headline. T, B and F are the ratios defined above.", ""]

    out += trend_section(lines, root, man)
    out += ["Run history", "-----------", "",
            "Every recorded run, newest first.", ""]
    rows = []
    for l in reversed(lines):
        if SUITE not in l.get("perf", {}):
            continue
        try:
            m = _manifest(l, root)
        except RuntimeError:
            m = None
        sc = [_fmt_x(normalize.score(l, SUITE, m, p, "T")) if m else "?" for p in ("cold", "warm")]
        flags = []
        if not l["valid"]:
            flags.append("invalid")
        if l.get("noisy"):
            flags.append("noisy")
        if l.get("dirty"):
            flags.append("dirty")
        if l.get("measured_later"):
            flags.append("re-measured")
        rows.append([_date(l["utc"])[:10], f"``{_short(l['commit'])}``", l["kind"],
                     (l.get("dvs") or {}).get("v") or "?", *sc, ", ".join(flags) or "ok"])
    out += _table(["date", "pyvsc", "kind", "dv-solve", "T cold", "T warm", "flags"], rows)
    out += [".. toctree::", "   :hidden:", "", "   methodology", ""]
    return "\n".join(out)


def trend_data(lines: list, root: Path, pat: str, arms: list) -> dict:
    """Per run: label, flags, and each arm's mean µs per call.

    Invalid runs are left out (their numbers may be wrong); noisy and dirty
    ones are kept and drawn hollow."""
    runs = [l for l in lines if l["valid"] and SUITE in l.get("perf", {})]
    labels, hollow, breaks, series, rows = [], set(), set(), {a: [] for a in arms}, []
    prev = None
    for i, l in enumerate(runs):
        man = _manifest(l, root)
        if prev is not None and man["hash"] != prev:
            breaks.add(i)
        prev = man["hash"]
        labels.append(f"{l['utc'][4:6]}-{l['utc'][6:8]}\n{_short(l['commit'])}")
        if l.get("noisy") or l.get("dirty"):
            hollow.add(i)
        row = [l["utc"], l["commit"], man["hash"], int(bool(l.get("noisy"))),
               int(bool(l.get("dirty")))]
        for a in arms:
            v = normalize.mean_us(l, SUITE, man, pat, a)
            series[a].append(v)
            row.append("" if v is None else f"{v:.3f}")
        rows.append(row)
    return {"labels": labels, "hollow": hollow, "breaks": breaks, "series": series,
            "csv_header": ["utc", "commit", "manifest", "noisy", "dirty"] + arms, "rows": rows}


def trend_section(lines: list, root: Path, man: dict) -> list:
    out = ["Over time", "---------", "",
           "Mean CPU µs per call for each arm, one point per recorded run (lower is faster).",
           "The mean is geometric over the suite's workloads, families weighted as in the",
           "headline, so one slow workload can't dominate it. ``cr`` lacks ``nested2``, so its",
           "mean covers six workloads. Open markers are runs on a busy host; a dashed",
           "vertical line marks a change of workload set, across which means aren't",
           "comparable. ``stock`` and ``cr`` never change, so their lines show the noise.", ""]
    for pat in man["patterns"]:
        out += [f".. image:: trend-{pat}.svg", f"   :alt: mean CPU µs per call over time, {pat}",
                "", f"**{pat}**: {PATTERN_TEXT.get(pat, pat)}. "
                f"Data: :download:`trend-{pat}.csv <trend-{pat}.csv>`.", ""]
    return out


def render(out_dir: Path, root: Path = HISTORY) -> list:
    lines = committed_lines(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "index.rst"
    p.write_text(index_page(lines, root))
    written = [p]
    cur = current(lines)
    if cur is not None:
        man = _manifest(cur, root)
        for pat in man["patterns"]:
            d = trend_data(lines, root, pat, man["arms"])
            sp = out_dir / f"trend-{pat}.svg"
            sp.write_text(svg.trend(d["labels"], d["series"],
                                    f"mean CPU µs per call, {pat} (log scale)",
                                    hollow=d["hollow"], breaks=d["breaks"]))
            cp = out_dir / f"trend-{pat}.csv"
            cp.write_text("\n".join(",".join(str(x) for x in r)
                                    for r in [d["csv_header"]] + d["rows"]) + "\n")
            written += [sp, cp]
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="doc/source/results")
    ap.add_argument("--require-run", action="store_true",
                    help="fail unless the history holds a valid run")
    ap.add_argument("--history", default=str(HISTORY))
    a = ap.parse_args(argv)
    root = Path(a.history)
    if a.require_run and current(committed_lines(root)) is None:
        print(f"error: {root} holds no valid run to publish", file=sys.stderr)
        return 1
    for p in render(Path(a.out), root):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
