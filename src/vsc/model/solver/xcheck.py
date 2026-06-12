"""XCHECK — differential cross-check of dv-solve against Boolector (Phase E / E1).

When enabled (``VSC_DVSOLVE_XCHECK=1``), every RandSet that dv-solve solves is
re-checked against Boolector: the dv-solve-produced model is asserted into a
freshly-built Boolector formula to confirm it is a *valid* model (membership),
and the bare problem's SAT/UNSAT verdict is compared.

This is differential testing as a *runtime mode*, not a one-off fuzzer: a user
can run their existing Boolector-validated regression under
``VSC_SOLVER=dv-solve VSC_DVSOLVE_XCHECK=1`` and get an automatic, per-RandSet
verdict on whether dv-solve agrees with the engine they trust. It is the
bug-reporting on-ramp for the adoption window (see
doc/notes/dv_solve_phaseE_selfsufficiency_plan.md §3).

Design notes:
  * It checks the *model dv-solve already produced* — it does **not** re-solve for
    values, so it runs **no swizzler and consumes no ``randstate``**. The only
    Boolector work is building the formula + ``Sat()``. Value streams are
    therefore unchanged whether XCHECK is on or off.
  * Value streams legitimately differ between engines, so XCHECK compares
    *semantic agreement* (verdict + membership), never exact values.
  * Mismatch policy: raise ``XCheckMismatch`` by default;
    ``VSC_DVSOLVE_XCHECK_WARN=1`` softens to a logged warning + a tally so a long
    run surfaces *all* mismatches instead of aborting on the first.
  * Sampling: ``VSC_DVSOLVE_XCHECK_RATE=p`` (0<p<=1) cross-checks a strided
    fraction of RandSets — deterministic and reproducible (no RNG).
"""
import os
import sys

from vsc.model.constraint_soft_model import ConstraintSoftModel


def _env_flag(name, default="0"):
    return os.environ.get(name, default) != "0"


_XCHECK_ENABLED = _env_flag("VSC_DVSOLVE_XCHECK")
_XCHECK_WARN = _env_flag("VSC_DVSOLVE_XCHECK_WARN")
try:
    _XCHECK_RATE = float(os.environ.get("VSC_DVSOLVE_XCHECK_RATE", "1.0"))
except ValueError:
    _XCHECK_RATE = 1.0

# Counters for strided sampling and warn-mode mismatch tallying.
_xcheck_seen = 0
_xcheck_tally = {"checked": 0, "skipped": 0, "mismatch": 0, "error": 0,
                 "unverifiable": 0}


class XCheckMismatch(Exception):
    """dv-solve and Boolector disagreed on a RandSet (a soundness signal)."""


# ----------------------------------------------------------------------- #
# Programmatic control (for harnesses that don't want to rely on env vars) #
# ----------------------------------------------------------------------- #

def set_xcheck(enabled=True, warn=None, rate=None):
    """Enable/disable XCHECK programmatically. Returns the previous settings as
    a (enabled, warn, rate) tuple so a test can restore them."""
    global _XCHECK_ENABLED, _XCHECK_WARN, _XCHECK_RATE
    prev = (_XCHECK_ENABLED, _XCHECK_WARN, _XCHECK_RATE)
    _XCHECK_ENABLED = bool(enabled)
    if warn is not None:
        _XCHECK_WARN = bool(warn)
    if rate is not None:
        _XCHECK_RATE = float(rate)
    return prev


def restore_xcheck(settings):
    """Restore the (enabled, warn, rate) tuple returned by ``set_xcheck``."""
    global _XCHECK_ENABLED, _XCHECK_WARN, _XCHECK_RATE
    _XCHECK_ENABLED, _XCHECK_WARN, _XCHECK_RATE = settings


def is_enabled():
    return _XCHECK_ENABLED


def get_tally():
    """Return a copy of the XCHECK counters (checked/skipped/mismatch/error)."""
    return dict(_xcheck_tally)


def reset_tally():
    global _xcheck_seen
    _xcheck_seen = 0
    for k in list(_xcheck_tally):
        _xcheck_tally[k] = 0


# ----------------------------------------------------------------------- #
# Sampling                                                                  #
# ----------------------------------------------------------------------- #

def _should_check():
    """Strided, deterministic sampling: with rate p, check every round(1/p)-th
    eligible RandSet. Reproducible run-to-run with no RNG (so a mismatch always
    reproduces). rate>=1 checks everything."""
    global _xcheck_seen
    idx = _xcheck_seen
    _xcheck_seen += 1
    if _XCHECK_RATE >= 1.0:
        return True
    if _XCHECK_RATE <= 0.0:
        return False
    stride = max(1, int(round(1.0 / _XCHECK_RATE)))
    return (idx % stride) == 0


# ----------------------------------------------------------------------- #
# The comparator                                                            #
# ----------------------------------------------------------------------- #

def xcheck_randset(rs, backend_name):
    """Cross-check the model dv-solve just produced for ``rs`` against Boolector.

    No-op unless XCHECK is enabled, the solving back-end was dv-solve, and this
    RandSet is selected by the sampling rate. Raises ``XCheckMismatch`` on a
    verdict/membership disagreement (unless warn-mode, which tallies + warns)."""
    if not _XCHECK_ENABLED:
        return
    # Only cross-check dv-solve's work; comparing Boolector to itself is pointless.
    if backend_name != "dv-solve":
        return
    if not _should_check():
        _xcheck_tally["skipped"] += 1
        return

    try:
        import pyboolector
        from pyboolector import Boolector
    except ImportError:
        # No oracle available — silently no-op (XCHECK needs Boolector).
        _xcheck_tally["skipped"] += 1
        return

    fields = list(rs.all_fields())
    rand_fields = [f for f in fields if getattr(f, "is_used_rand", False)]
    hard = [c for c in rs.constraints() if not isinstance(c, ConstraintSoftModel)]

    # Faithfulness guard: if there are constraints but the comparator captured no
    # rand fields to pin (e.g. an inline ``randomize_with`` whose rand vars are
    # not in this RandSet's ``all_fields()``), the comparator cannot reconstruct
    # the problem dv-solve actually solved — every field would build as a ground
    # Const and the bare formula's verdict is meaningless. ABSTAIN rather than
    # emit a finding we can't substantiate: a cross-check tool that cries wolf
    # destroys the trust it exists to build. Tallied as "unverifiable".
    if hard and not rand_fields:
        _xcheck_tally["unverifiable"] += 1
        return

    # Snapshot the dv-solve model BEFORE building (build() does not mutate val,
    # but capture defensively). Mask to width so signed negatives become the
    # correct two's-complement bit pattern for an Eq comparison.
    dv_model = {}
    for f in rand_fields:
        mask = (1 << f.width) - 1
        dv_model[id(f)] = int(f.get_val()) & mask

    btor = Boolector()
    btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_INCREMENTAL, True)
    btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_MODEL_GEN, True)

    try:
        nodes = {id(f): f.build(btor) for f in fields}
        cnodes = [c.build(btor) for c in hard]

        # (1) Verdict: is the bare hard-constraint problem SAT for Boolector?
        for cn in cnodes:
            btor.Assume(cn)
        verdict_sat = (btor.Sat() == btor.SAT)

        # (2) Membership: pin the dv-solve model; is it still SAT?
        for cn in cnodes:
            btor.Assume(cn)
        for f in rand_fields:
            const = btor.Const(dv_model[id(f)], f.width)
            btor.Assume(btor.Eq(nodes[id(f)], const))
        membership_sat = (btor.Sat() == btor.SAT)
    except XCheckMismatch:
        raise
    except Exception as e:  # noqa: BLE001 - a build/oracle error must not crash randomize
        _xcheck_tally["error"] += 1
        _warn("XCHECK could not build the Boolector oracle for a RandSet "
              "(skipped): %s" % e)
        return
    finally:
        for f in fields:
            f.dispose()

    _xcheck_tally["checked"] += 1

    # dv-solve produced a model, so the problem is SAT by construction. Boolector
    # disagreeing on the verdict, or rejecting the specific model, is a mismatch.
    if not membership_sat or not verdict_sat:
        _xcheck_tally["mismatch"] += 1
        detail = _describe(rs, rand_fields, dv_model, verdict_sat, membership_sat)
        if _XCHECK_WARN:
            _warn("XCHECK MISMATCH (warn): %s" % detail)
            return
        raise XCheckMismatch(detail)


def _describe(rs, rand_fields, dv_model, verdict_sat, membership_sat):
    if not membership_sat and verdict_sat:
        kind = ("dv-solve produced a model that VIOLATES the constraints "
                "(Boolector finds the problem SAT but rejects this model) — "
                "a mis-encoding")
    elif not verdict_sat:
        kind = ("dv-solve produced a model but Boolector finds the problem "
                "UNSAT — a verdict disagreement")
    else:
        kind = "unexpected"
    lines = ["%s." % kind, "  dv-solve model:"]
    for f in rand_fields:
        lines.append("    %s = %d (width=%d, signed=%s)" % (
            f.get_full_name(), dv_model[id(f)], f.width,
            getattr(f, "is_signed", False)))
    lines.append("  hard constraints: %d" % len(
        [c for c in rs.constraints() if not isinstance(c, ConstraintSoftModel)]))
    return "\n".join(lines)


def _warn(msg):
    print("vsc: " + msg, file=sys.stderr)
