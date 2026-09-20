"""Kill-switches for the Stage 1 overhead-removal steps.

Each Stage 1 optimization lands behind one of these, defaulting to **on**, so a
regression can be bisected to a single step without a rebuild or a revert, and
so ``all off`` reproduces the pre-Stage-1 tree exactly. See
``doc/notes/vdc_stage1_impl_plan.md`` §S1.1 and §3.6.

They are read from the environment at import and are plain module attributes,
so a benchmark can flip them in-process and time the same live objects both
ways (the idiom ``benchmarks/bench_optimizations.py`` already uses).
"""
import os


def _env(name, default=True):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.lower() not in ("0", "", "false", "no", "off")


#: S1.2 — read solved values back with one bulk FFI call per RandSet instead of
#: one call per field.
BULK_READBACK = _env("VSC_S1_BULK_READBACK")

#: S1.3 — skip copying an enabled rand field's stale instance value into the
#: model before a solve that is about to overwrite it.
SKIP_COPYIN = _env("VSC_S1_SKIP_COPYIN")

#: S1.4 — run the housekeeping model walks only for types that can actually be
#: affected by them (soft priorities, override rollback, user hooks).
LAZY_WALKS = _env("VSC_S1_LAZY_WALKS")

#: S1.7 — track only *constraint-referenced* non-rand field values in the
#: Tier-A plan's freshness signature, instead of every field in ``bound_m``.
NARROW_PLAN_SIG = _env("VSC_S1_NARROW_PLAN_SIG")


def set_all(on):
    """Set every Stage 1 switch at once (benchmark/bisect helper)."""
    global BULK_READBACK, SKIP_COPYIN, LAZY_WALKS, NARROW_PLAN_SIG
    BULK_READBACK = SKIP_COPYIN = LAZY_WALKS = NARROW_PLAN_SIG = bool(on)


def snapshot():
    return {"BULK_READBACK": BULK_READBACK, "SKIP_COPYIN": SKIP_COPYIN,
            "LAZY_WALKS": LAZY_WALKS, "NARROW_PLAN_SIG": NARROW_PLAN_SIG}
