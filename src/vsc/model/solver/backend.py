# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Created on Jun 9, 2026
#
# Solver back-end interface and selection. See
# doc/notes/dv_solve_integration_design.md (§4) for the design.

from typing import Dict


class BackendIncomplete(Exception):
    """Raised by a back-end to request fallback to another back-end for a
    RandSet.

    This is an internal control-flow signal: it means the back-end cannot
    (yet) handle some construct in the RandSet, but the problem is not known
    to be UNSAT. The Randomizer responds by retrying the same RandSet on the
    next available back-end (Phase 2). A bare/abstract back-end raises this
    rather than producing a wrong answer.

    ``reason_code`` is a coarse category (e.g. ``"dist"``, ``"array"``,
    ``"width"``, ``"search-incomplete"``, ``"bvsat-undecided"``) used by the
    fallback telemetry (SolveInfo.fallback_reasons) to drive the per-phase
    burn-down. Defaults to ``"incomplete"`` when a raise site doesn't classify
    itself.
    """

    def __init__(self, *args, reason_code="incomplete"):
        super().__init__(*args)
        self.reason_code = reason_code


class SolveResult(object):
    """Optional result struct returned by ``solve_randset`` to feed
    ``SolveInfo``. ``solve_randset`` writes solved values directly into the
    RandSet's fields; this carries solve statistics back to the caller.
    """

    def __init__(self, status=0, n_sat_calls=0):
        self.status = status
        self.n_sat_calls = n_sat_calls


class SolverBackendIF(object):
    """Interface a solver back-end implements so the Randomizer can drive it
    without knowing which engine is underneath.

    Capability flags let the Randomizer adapt (e.g. skip the swizzler when the
    back-end randomizes internally, or skip ``dist`` expansion when the
    back-end consumes ``dist`` natively).
    """

    # Display / selection name (e.g. "boolector", "dv-solve").
    name = "<abstract>"

    # True => the back-end honors soft constraints itself.
    supports_soft = False

    # True => the back-end consumes ``ConstraintDistModel`` natively, so the
    # DistConstraintBuilder expansion should be skipped for it.
    supports_dist_native = False

    # True => the back-end produces a randomized solution itself, so the
    # Randomizer skips the Boolector swizzler.
    randomizes_internally = False

    @classmethod
    def available(cls) -> bool:
        """Return True if this back-end can be used in the current
        environment (native lib / Python module importable)."""
        return False

    def solve_randset(self,
                      rs,
                      bound_m: Dict,
                      randstate,
                      solve_info=None,
                      debug=0) -> "SolveResult":
        """Build, solve, and write solved values back into ``rs``'s fields.

        Raises ``SolveFailure`` on UNSAT. May raise ``BackendIncomplete`` to
        request fallback to another back-end for this RandSet.
        """
        raise NotImplementedError(
            "%s does not implement solve_randset" % type(self).__name__)


# ------------------------------------------------------------------ #
# Back-end selection                                                   #
# ------------------------------------------------------------------ #

# Canonical names and accepted aliases.
_ALIASES = {
    "boolector": "boolector",
    "btor": "boolector",
    "dv-solve": "dv-solve",
    "dv_solve": "dv-solve",
    "dvsolve": "dv-solve",
    "auto": "auto",
}


def _load_backend_cls(name: str):
    """Lazily import and return the back-end class for a canonical name.

    Imports are deferred so that, e.g., selecting dv-solve does not import
    pyboolector and vice-versa (relevant once Boolector becomes optional).
    """
    if name == "boolector":
        from vsc.model.solver.boolector_backend import BoolectorBackend
        return BoolectorBackend
    elif name == "dv-solve":
        from vsc.model.solver.dvsolve_backend import DvSolveBackend
        return DvSolveBackend
    else:
        raise Exception("Unknown solver back-end '%s'" % name)


def select_backend(name: str) -> SolverBackendIF:
    """Resolve a back-end name to an instantiated, available back-end.

    ``auto`` prefers dv-solve (which can always solve *something* via its
    Python engine, once present) and falls back to Boolector. During the
    integration the dv-solve back-end may not yet be present, in which case
    ``auto`` resolves to Boolector.

    Raises a clear error if the requested back-end is not available.
    """
    canon = _ALIASES.get((name or "").lower())
    if canon is None:
        raise Exception(
            "Unknown solver back-end '%s' (expected one of: %s)" % (
                name, ", ".join(sorted(set(_ALIASES.values())))))

    if canon == "auto":
        # Prefer dv-solve, fall back to Boolector.
        for candidate in ("dv-solve", "boolector"):
            try:
                cls = _load_backend_cls(candidate)
            except Exception:
                continue
            if cls.available():
                return cls()
        raise Exception(
            "No solver back-end is available for VSC_SOLVER=auto "
            "(tried dv-solve, boolector)")

    cls = _load_backend_cls(canon)
    if not cls.available():
        raise Exception(
            "Solver back-end '%s' is not available in this environment" % canon)
    return cls()
