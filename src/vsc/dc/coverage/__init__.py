"""
``vsc.dc.coverage`` — the dataclass coverage front-end (surfaced as ``vdc.*``).

Coverpoints/crosses are declared as class-level descriptors; structure is
elaborated once per type (``CovergroupTypeModel``) and the per-instance runtime
delegates to pyvsc's existing IEEE-1800-faithful coverage model. The bin
specification helpers (``bin``/``bin_array``/``wildcard_bin``) are re-exported from
the classic implementation unchanged — same SV semantics.
"""
from .covergroup import Covergroup
from .descriptors import Coverpoint, Cross, coverpoint, cross

# Reuse the classic, SV-1800-faithful bin specifications verbatim.
from vsc.coverage import bin, bin_array, wildcard_bin  # noqa: F401

__all__ = [
    "Covergroup", "Coverpoint", "Cross", "coverpoint", "cross",
    "bin", "bin_array", "wildcard_bin",
]
