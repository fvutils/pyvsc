#!/usr/bin/env bash
#
# Run the full ve/unit suite under every solver back-end.
#
# The back-end is selected by the VSC_SOLVER env var (boolector | dv-solve),
# read at import time, so the only robust way to exercise a back-end across the
# whole suite is a fresh process per back-end. This script runs the suite once
# per back-end and fails if any run fails.
#
# Mirrors the CI matrix (.github/workflows/ci.yml ci-linux). dv-solve must be
# importable for that leg; if it is not, that leg is skipped with a warning
# rather than failing, so the script is usable in a boolector-only checkout.
#
# Extra args are forwarded to pytest, e.g.
#   ve/run_all_backends.sh -v
#   ve/run_all_backends.sh -k array
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"

# Same exclusions as the CI ci-linux job (flaky/seed-sensitive or
# back-end-irrelevant suites).
mapfile -t tests < <(ls ve/unit/*.py \
    | grep -v test_random_dist \
    | grep -v vsc_test_case \
    | grep -v test_covergroup_programmatic \
    | grep -v test_rand_mode)

backends=(boolector dv-solve)
overall=0

for solver in "${backends[@]}"; do
    if [ "$solver" = "dv-solve" ]; then
        if ! "$PYTHON" -c "from vsc.model.solver.dvsolve_backend import DvSolveBackend; raise SystemExit(0 if DvSolveBackend.available() else 1)" 2>/dev/null; then
            echo "== SKIP back-end '$solver': not available in this environment =="
            continue
        fi
    fi
    echo "== ve/unit under VSC_SOLVER=$solver =="
    VSC_SOLVER="$solver" "$PYTHON" -m pytest --no-cov -q "${tests[@]}" "$@"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "== FAIL under VSC_SOLVER=$solver (exit $rc) =="
        overall=1
    else
        echo "== PASS under VSC_SOLVER=$solver =="
    fi
done

exit "$overall"
