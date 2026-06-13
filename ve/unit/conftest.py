"""Local pytest config for the ve/unit suite.

Phase F / F-0a — the self-sufficiency audit reporter. When
``VSC_DVSOLVE_FALLBACK_TALLY=1`` is set, this prints the suite-wide dv-solve
fallback histogram (``randomizer.get_fallback_tally``) at the end of the run, so a
single command answers "which RandSets does dv-solve still defer to Boolector?".

It is **completely inert** unless that env var is set — normal test runs see no
behavior change. Pair it with the audit env to enumerate dv-solve's serving
dependencies:

    # what still defers even with serve-SAT on (the F-2 work list / F-3 blockers):
    PYTHONPATH=src VSC_SOLVER=dv-solve \
      VSC_DVSOLVE_BVSAT_SERVE_SAT=1 VSC_DVSOLVE_FALLBACK_TALLY=1 \
      python -m pytest --no-cov -q ve/unit

The tally is process-global, so a test that measures its own corpus must restore
it afterward or it corrupts this suite-wide number. The three meta-tests that do
so (``test_dvsolve_fallback_histogram``, ``_xcheck``, ``_solve_order_native``)
snapshot/restore via ``randomizer.snapshot_fallback_tally`` /
``restore_fallback_tally``, so they can be left in the audit run.

The ``:hard`` suffix on a code marks a *re-raised* defer (strict
``VSC_DVSOLVE_NO_FALLBACK`` mode — nothing could serve it); a bare code marks a
defer the fallback then served. See doc/notes/dv_solve_phaseF_retirement_plan.md.
"""
import os


def _tally_enabled():
    return os.environ.get("VSC_DVSOLVE_FALLBACK_TALLY", "0") not in ("0", "")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _tally_enabled():
        return
    try:
        import vsc.model.randomizer as rnd
        hist = rnd.get_fallback_tally()
    except Exception as e:  # pragma: no cover - diagnostic only
        terminalreporter.write_line(
            "[dv-solve self-sufficiency audit] tally unavailable: %s" % e)
        return

    tr = terminalreporter
    tr.write_sep("=", "dv-solve self-sufficiency audit (suite-wide fallback tally)")
    if not hist:
        tr.write_line("  (no fallbacks — dv-solve served every RandSet itself)")
        tr.write_sep("=", "")
        return

    served = {k: v for k, v in hist.items() if not k.endswith(":hard")}
    hard = {k: v for k, v in hist.items() if k.endswith(":hard")}
    total = sum(hist.values())

    tr.write_line("  served by fallback (dv-solve deferred, Boolector served):")
    for k in sorted(served):
        tr.write_line("    %-26s %d" % (k, served[k]))
    if hard:
        tr.write_line("  HARD-FAIL (strict no-fallback — nothing served it):")
        for k in sorted(hard):
            tr.write_line("    %-26s %d" % (k, hard[k]))
    tr.write_line("  ---")
    tr.write_line("  total fallback events: %d" % total)
    tr.write_sep("=", "")
