"""Fold a `perf record -g` capture of a `python -X perf` process into reports.

    perf record -F 2000 -g -o out.data -- python -X perf <program>
    perf script -i out.data > out.txt
    python3 benchmarks/profile_fold.py out.txt [--root _run_phase] [--top 40]
        [--buckets] [--folded out.folded]

Python frames come from CPython's perf trampoline (`py::<func>:<file>`, read
through /tmp/perf-<pid>.map); native frames keep their DSO. Only samples whose
stack contains a Python frame named --root are kept, which restricts the report
to the timed region (for riscv_dv_child.py, pygen's `_run_phase`) and drops
start-up, imports and other threads.

Weights are the sampled cycle counts, so percentages are of CPU cycles in the
region. Reports:

  native leaf     the DSO the sample landed in (interpreter, libc, dv-solve, ...)
  inclusive       Python functions by share of samples with them on the stack
  self            the innermost Python function, plus the native DSO under it
  buckets         samples assigned to the innermost matching phase rule
  --folded        Brendan Gregg folded stacks (root first), for a flame graph
"""
from __future__ import annotations

import argparse
import collections
import re
import sys

_HDR = re.compile(r"^\S.*?\s(\d+)\s+cycles")
_FRAME = re.compile(r"^\s+[0-9a-f]+\s+(.*?)\s+\((.*)\)$")


def _short_dso(dso: str) -> str:
    base = dso.rsplit("/", 1)[-1]
    if base.startswith("perf-") and base.endswith(".map"):
        return "py"
    if base.startswith("python3"):
        return "cpython"
    if base.startswith("libdv_solve"):
        return "dv-solve (C)"
    if base.startswith("libc.so"):
        return "libc"
    if base.startswith(("_ctypes", "libffi")):
        return "ctypes/ffi"
    if "openblas" in base:
        return "openblas"
    if base == "[unknown]":
        return "kernel/unknown"
    return base


def _frame_name(sym: str, dso: str) -> str:
    if sym.startswith("py::"):
        name = sym[4:].rsplit("+0x", 1)[0]
        func, _, path = name.partition(":")
        path = re.sub(r".*/(src/vsc|pygen_src|dv_solve|benchmarks/perf|python3\.12)/", r"\1/", path)
        return f"{func} [{path}]"
    return f"{sym.rsplit('+0x', 1)[0]} <{_short_dso(dso)}>"


def samples(path: str):
    """Yield (weight, frames innermost-first as (name, dso_short, is_py))."""
    weight, frames = None, []
    with open(path, errors="replace") as f:
        for line in f:
            if not line.strip():
                if weight is not None:
                    yield weight, frames
                weight, frames = None, []
                continue
            m = _HDR.match(line)
            if m:
                weight, frames = int(m.group(1)), []
                continue
            m = _FRAME.match(line)
            if m and weight is not None:
                sym, dso = m.group(1), m.group(2)
                frames.append((_frame_name(sym, dso), _short_dso(dso), sym.startswith("py::")))
    if weight is not None:
        yield weight, frames


# Phase entry points. A sample belongs to the innermost entry point on its
# stack, so generic helpers (ModelVisitor.visit_*, Expr*.accept, copy.*) are
# charged to the phase that called them. Patterns match "<qualname> [<file>]".
BUCKETS = [
    # dv-solve, innermost first
    ("dv-solve: native solve + readback", r"DvSolveBackend\._solve_and_readback |SolveCtx\.(solve|get_value)"),
    ("dv-solve: native compile", r"_make_solve_ctx |SolveCtx\.__init__ "),
    ("dv-solve: builder (Python->C problem)", r"SolveProblemBuilder\."),
    ("dv-solve: bvsat", r"\[dv_solve/bvsat"),
    # pyvsc's dv-solve back-end
    ("backend: domain membership (enum/in-ranges)", r"DvSolveExprTranslator\.try_native_in_ranges |DvSolveBackend\._membership_expr |DvSolveBackend\._domain_of "),
    ("backend: translate constraints", r"DvSolveExprTranslator\.translate "),
    ("backend: other", r"DvSolveBackend\."),
    # Boolector
    ("boolector: build + solve", r"\[src/vsc/model/solver/boolector_backend|pyboolector|Boolector"),
    # pyvsc randomizer phases
    ("randomizer: variable bounds", r"VariableBoundVisitor\.process "),
    ("randomizer: array/dist expansion", r"(ArrayConstraintBuilder|DistConstraintBuilder)\.build "),
    ("randomizer: randset partition", r"RandInfoBuilder\.build "),
    ("randomizer: post_randomize", r"\.post_randomize \[src/vsc"),
    ("randomizer: pre_randomize/set_used_rand/soft", r"\.(pre_randomize|set_used_rand) \[src/vsc|ClearSoftPriorityVisitor"),
    ("randomizer: override rollback", r"ConstraintOverrideRollbackVisitor"),
    ("randomizer: solve loop other", r"Randomizer\.(randomize|_solve_randset) "),
    ("randomizer: do_randomize other", r"Randomizer\.do_randomize "),
    # pyvsc front-end
    ("front-end: randomize_with exit", r"__exit__ \[src/vsc/rand_obj"),
    ("front-end: model build", r"build_field_model \[src/vsc/rand_obj"),
    ("front-end: other pyvsc", r"\[src/vsc/"),
    # pygen
    ("pygen: instruction deepcopy", r"(^|\.)deepcopy \[python3\.12/copy"),
    ("pygen: other", r"\[pygen_src/"),
]
_BUCKETS = [(n, re.compile(p)) for n, p in BUCKETS]


# Catch-alls apply only when no specific entry point is on the stack.
_CATCH_ALL = {"front-end: other pyvsc", "pygen: other"}


def bucket_of(frames) -> str:
    for rules in ([r for r in _BUCKETS if r[0] not in _CATCH_ALL],
                  [r for r in _BUCKETS if r[0] in _CATCH_ALL]):
        for name, _, _ in frames:      # innermost first; native frames too (pyboolector)
            for b, rx in rules:
                if rx.search(name):
                    return b
    return "(no python frame)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("perf_script")
    ap.add_argument("--root", default="_run_phase")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--buckets", action="store_true")
    ap.add_argument("--folded")
    a = ap.parse_args(argv)

    total = 0
    leaf = collections.Counter()
    incl = collections.Counter()
    selfc = collections.Counter()
    bk = collections.Counter()
    bk_native = collections.defaultdict(collections.Counter)
    folded = collections.Counter()
    root_rx = re.compile(r"(^|\.)" + re.escape(a.root) + r" ")
    for w, frames in samples(a.perf_script):
        if not any(py and root_rx.search(n) for n, _, py in frames):
            continue
        total += w
        leaf[frames[0][1] if frames else "?"] += w
        seen = set()
        for n, _, py in frames:
            if py and n not in seen:
                seen.add(n)
                incl[n] += w
        py_leaf = next((n for n, _, py in frames if py), "?")
        native = frames[0][1] if frames and not frames[0][2] else None
        selfc[py_leaf + (f"  -> {native}" if native and native != "cpython" else "")] += w
        b = bucket_of(frames)
        bk[b] += w
        bk_native[b][frames[0][1] if frames else "?"] += w
        if a.folded:
            names = [n for n, _, py in frames if py]
            if native and native not in ("cpython",):
                names.insert(0, f"[{native}]")
            folded[";".join(reversed(names))] += w
    if not total:
        print(f"no samples under {a.root}", file=sys.stderr)
        return 1

    pct = lambda v: 100.0 * v / total            # noqa: E731
    print(f"samples under {a.root}: {total:,} cycles (sampled)\n")
    print("native leaf (where the CPU was):")
    for k, v in leaf.most_common():
        print(f"  {pct(v):5.1f}%  {k}")
    if a.buckets:
        print("\nphase buckets (innermost matching Python frame):")
        for k, v in bk.most_common():
            nat = ", ".join(f"{n} {100.0 * c / v:.0f}%" for n, c in bk_native[k].most_common(3))
            print(f"  {pct(v):5.1f}%  {k:42s} [{nat}]")
    print(f"\ninclusive (top {a.top}):")
    for k, v in incl.most_common(a.top):
        print(f"  {pct(v):5.1f}%  {k}")
    print(f"\nself (top {a.top}):")
    for k, v in selfc.most_common(a.top):
        print(f"  {pct(v):5.1f}%  {k}")
    if a.folded:
        with open(a.folded, "w") as f:
            for k, v in folded.items():
                f.write(f"{k} {v}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
