"""Arms: a front-end, a back-end and a build (design §3).

Headline ratios (§6.1), each a ratio of CPU time per call measured in the
same run, so >1 means the second arm is faster:

    B  = classic-btor / classic-dvs     what the back-end buys
    F  = classic-dvs  / dc-dvs          what the front-end buys
    T  = classic-btor / dc-dvs          what the whole stack buys
    S  = stock        / dc-dvs          today's stack vs pyvsc 0.9.5 as installed
    S0 = stock        / classic-btor    today vs 0.9.5 for a user who changes nothing

`dc-btor` completes the 2×2 so F can be checked independently of the back-end.
`cr` is constrainedrandom: recorded where it can express the workload, never
in a pyvsc headline.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arm:
    name: str
    frontend: str            # classic | dc | cr
    backend: str | None      # vsc.set_solver_backend() name; None: the build's default
    build: str               # head | stock | cr (perf.builds)


ARMS = {a.name: a for a in (
    Arm("classic-btor", "classic", "boolector", "head"),
    Arm("classic-dvs", "classic", "dv-solve", "head"),
    Arm("dc-btor", "dc", "boolector", "head"),
    Arm("dc-dvs", "dc", "dv-solve", "head"),
    Arm("stock", "classic", None, "stock"),
    Arm("cr", "cr", None, "cr"),
)}

# name -> (numerator arm, denominator arm)
RATIOS = {
    "T": ("classic-btor", "dc-dvs"),
    "B": ("classic-btor", "classic-dvs"),
    "F": ("classic-dvs", "dc-dvs"),
    "S": ("stock", "dc-dvs"),
    "S0": ("stock", "classic-btor"),
    "B_dc": ("dc-btor", "dc-dvs"),
    "F_btor": ("classic-btor", "dc-btor"),
}
HEADLINE = ("T", "B", "F", "S", "S0")
