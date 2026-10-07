"""Suite manifests (design §4.2): suites/<name>.json resolved against the registry.

The resolved manifest fixes the order of the per-cell arrays in a trend line
and records each workload's rev and source hash; its hash names it in
history/manifests/.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import workloads
from .arms import ARMS

HERE = Path(__file__).resolve().parent / "suites"


def names() -> list:
    return sorted(p.stem for p in HERE.glob("*.json"))


def load(name: str) -> dict:
    spec = json.loads((HERE / f"{name}.json").read_text())
    spec.pop("_comment", None)
    spec["name"] = name
    unknown = [a for a in spec["arms"] if a not in ARMS]
    if unknown:
        raise ValueError(f"suite {name}: unknown arms {unknown}")
    reg = workloads.all_workloads()
    missing = [w for w in spec["workloads"] if w not in reg]
    if missing:
        raise ValueError(f"suite {name}: unknown workloads {missing}")
    spec["manifest"] = manifest(spec, reg)
    return spec


def manifest(spec: dict, reg: dict) -> dict:
    man = {
        "suite": spec["name"],
        "workloads": [{"name": w, "family": reg[w].family, "rev": reg[w].rev,
                       "sha": workloads.source_sha(reg[w]),
                       "frontends": workloads.frontends(reg[w])}
                      for w in spec["workloads"]],
        "arms": list(spec["arms"]),
        "patterns": list(spec["patterns"]),
        "family_weights": spec.get("family_weights", {}),
        # the measurement protocol: changing it starts a new trend line
        "protocol": {"batch_s": spec.get("batch_s", 0.3), "rounds": spec.get("rounds", 2),
                     "timeout_s": spec.get("timeout_s", 60)},
    }
    man["hash"] = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()[:12]
    return man
