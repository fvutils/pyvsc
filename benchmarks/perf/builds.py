"""Builds: where each arm's code under test comes from (design §7.2).

    head    the working tree's src/, with dv-solve and pyboolector from the
            interpreter running the harness
    stock   pyvsc 0.9.5 + pyboolector from PyPI, side-installed (the anchor)
    cr      constrainedrandom 1.3.0, side-installed (the external reference)

Side installs go under build/perf/builds/<name>/ with `pip install --target`,
pinned in tools.lock.json, and are redone when the pin changes. A failed
install fails the run: the anchor is never silently dropped.

    python3 -m perf.builds            # install or refresh the side builds
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCK_PATH = HERE / "tools.lock.json"
LOCK = json.loads(LOCK_PATH.read_text())
ROOT = REPO / "build" / "perf" / "builds"


def lock_sha() -> str:
    return hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest()[:12]


def _installer(target: Path, pins: list) -> list:
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "-q", "--python", sys.executable,
                "--target", str(target), *pins]
    return [sys.executable, "-m", "pip", "install", "-q", "--target", str(target), *pins]


def ensure(name: str) -> Path:
    """The side-install directory for build `name`, installing it if needed."""
    pins = LOCK["builds"][name]
    target = ROOT / name
    stamp = target / ".perf-pins"
    want = json.dumps(pins)
    if stamp.exists() and stamp.read_text() == want:
        return target
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    r = subprocess.run(_installer(target, pins), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"side install of {name} ({' '.join(pins)}) failed:\n{r.stderr[-2000:]}")
    stamp.write_text(want)
    return target


def pythonpath(build: str) -> list:
    """sys.path entries a child of this build gets, ahead of site-packages.

    benchmarks/ comes last so the child can import perf.child and the
    workload registry, which import nothing from pyvsc at module scope."""
    bench = str(REPO / "benchmarks")
    if build == "head":
        return [str(REPO / "src"), bench]
    return [str(ensure(build)), bench]


def _git(args: list, cwd: Path):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def tree_state(path: Path, pathspec: str = ".") -> dict:
    """Commit and dirty flag of the git tree at path (tracked files only)."""
    commit = _git(["rev-parse", "HEAD"], path)
    dirty = bool(_git(["status", "--porcelain", "--untracked-files=no", "--", pathspec], path))
    return {"commit": commit, "dirty": dirty}


def main() -> int:
    for name in LOCK["builds"]:
        print(name, ensure(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
