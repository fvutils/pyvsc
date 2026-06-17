"""
``vsc.dc`` — the dataclass front-end for pyvsc (import as ``vdc``).

Per-type elaboration: field layout and constraint structure are computed once at
class-decoration time and cached on the class, then reused across all instances.
Targets pyvsc's existing model + ``dv-solve`` back-end unchanged.

    import vsc.dc as vdc

    @vdc.dataclass
    class AluTxn(vdc.RandClass):
        op: vdc.u4  = vdc.rand()
        a:  vdc.u32 = vdc.rand()
        b:  vdc.u32 = vdc.rand()

        @vdc.constraint
        def c_op(self):
            self.op <= 7
            self.a < self.b

See ``doc/notes/dataclass-pyvsc-design.md`` and
``doc/notes/dataclass_pyvsc_impl_test_doc_plan.md``.
"""
from .api import randomize, randomize_with
from .coverage import (Coverpoint, Covergroup, Cross, bin, bin_array,  # noqa: F401
                       coverpoint, cross, wildcard_bin)
from .decorators import constraint, dataclass
from .fields import cg_arg, field, rand, randc, sample_arg
from .rand_class import RandClass
from .types import bitv  # noqa: F401  (u1..u64 / s1..s64 imported via * below)
from . import types as _types

# Constraint helpers. These are AST-recognized in @vdc.constraint bodies (never
# executed there), but are re-exported so the names resolve and can be used in
# inline randomize_with blocks. They map to pyvsc's existing helpers.
from vsc.constraints import (else_if, else_then, foreach, if_then, implies,  # noqa: F401
                             solve_order, soft, unique, unique_vec, weight, dist)
from vsc.types import rangelist, rng  # noqa: F401
from vsc.model.solve_failure import SolveFailure  # noqa: F401

# Re-export the generated width aliases (u1..u64, s1..s64).
for _n in _types.__all__:
    if _n[0] in ("u", "s") and _n[1:].isdigit():
        globals()[_n] = getattr(_types, _n)
del _n

__all__ = [
    "dataclass", "constraint",
    "rand", "randc", "field", "cg_arg", "sample_arg",
    "RandClass", "randomize", "randomize_with",
    "Covergroup", "Coverpoint", "Cross", "coverpoint", "cross",
    "bin", "bin_array", "wildcard_bin",
    "bitv",
    "if_then", "else_if", "else_then", "implies", "foreach",
    "soft", "unique", "unique_vec", "solve_order", "weight", "dist", "rangelist",
    "rng", "SolveFailure",
] + [n for n in _types.__all__ if n[0] in ("u", "s") and n[1:].isdigit()]
