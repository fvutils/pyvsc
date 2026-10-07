"""Ratios and suite scores from trend lines (design §6).

Everything works on trend lines (or run records turned into them), so the
pages, consolidation and ad-hoc analysis compute identical numbers. A ratio
is t(numerator arm) / t(denominator arm) for one workload and pattern, both
measured in the same run; > 1 means the denominator arm is faster. A cell
that is n/a, failed or timed out never enters a ratio.

Suite scores are category-weighted geometric means (dv-solve §5.4): families
are the categories, weights come from the manifest, and no family may carry
more than CAP of a score. Weights are a view property: the same function
recomputes every historical point with the current weights.
"""
from __future__ import annotations

import math

from .arms import RATIOS

CAP = 0.40


def cells(line: dict, suite: str) -> dict:
    """{(workload, pattern, arm): cpu µs} for one suite of a trend line."""
    p = line.get("perf", {}).get(suite)
    if not p:
        return {}
    out = {}
    for w, rows in p["w"].items():
        for pat, row in zip(p["pat"], rows):
            for arm, v in zip(p["arms"], row):
                if v is not None:
                    out[(w, pat, arm)] = v
    return out


def ratio(c: dict, w: str, pat: str, name: str):
    num, den = RATIOS[name]
    a, b = c.get((w, pat, num)), c.get((w, pat, den))
    return a / b if a and b else None


def family_shares(families: list, weights: dict) -> dict:
    """Family -> share of the score, weights capped at CAP and renormalised.

    With fewer than 1/CAP families the cap can't be met; shares then stay
    proportional to the weights."""
    fams = sorted(set(families))
    w = {f: float(weights.get(f, 1.0)) for f in fams}
    tot = sum(w.values())
    share = {f: w[f] / tot for f in fams}
    if len(fams) * CAP < 1.0:
        return share
    for _ in range(len(fams)):
        over = {f for f, s in share.items() if s > CAP + 1e-12}
        if not over:
            break
        rest = [f for f in fams if f not in over]
        spare = 1.0 - CAP * len(over)
        rw = sum(w[f] for f in rest)
        share = {f: (CAP if f in over else spare * w[f] / rw) for f in fams}
    return share


def score(line: dict, suite: str, manifest: dict, pat: str, name: str):
    """Category-weighted geomean of ratio `name` over a suite, or None."""
    c = cells(line, suite)
    fam = {w["name"]: w["family"] for w in manifest["workloads"]}
    logs = {}
    for w in fam:
        r = ratio(c, w, pat, name)
        if r:
            logs.setdefault(fam[w], []).append(math.log(r))
    if not logs:
        return None
    share = family_shares(list(logs), manifest.get("family_weights", {}))
    return math.exp(sum(share[f] * sum(v) / len(v) for f, v in logs.items()))


def manifest_from_line(line: dict, suite: str, families: dict) -> dict:
    """A minimal manifest when only the line and the registry's families are at hand."""
    p = line["perf"][suite]
    return {"workloads": [{"name": w, "family": families.get(w, "scalar")} for w in p["w"]],
            "family_weights": {}}


def mean_us(line: dict, suite: str, manifest: dict, pat: str, arm: str):
    """Family-weighted geometric mean of an arm's CPU µs per call, or None.

    The same weighting as score(), over the workloads the arm measured.
    Comparable across runs only while the manifest (the workload set) is the
    same, which is why the trend chart breaks its lines where it changes."""
    c = cells(line, suite)
    logs = {}
    for w in manifest["workloads"]:
        v = c.get((w["name"], pat, arm))
        if v:
            logs.setdefault(w["family"], []).append(math.log(v))
    if not logs:
        return None
    share = family_shares(list(logs), manifest.get("family_weights", {}))
    return math.exp(sum(share[f] * sum(v) / len(v) for f, v in logs.items()))
