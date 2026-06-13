#!/usr/bin/env bash
#
# F-0b — run the dv-solve XCHECK soak corpus.
#
# Runs every test in ve/xcheck_corpus.txt under the dv-solve back-end with the
# differential cross-check enabled, so each RandSet dv-solve solves is re-checked
# against a Boolector-built formula (verdict + membership). A mismatch fails the
# run. This is the engine of the F-4 default-flip gate (parent plan §6 / F-4c):
# the corpus must stay XCHECK-clean for the soak period before dv-solve becomes
# the global default.
#
# Requires both dv-solve (the native back-end under test) and pyboolector (the
# XCHECK oracle) to be importable. Extra args are forwarded to pytest, e.g.
#   ve/run_xcheck_soak.sh -v
#   ve/run_xcheck_soak.sh -k ubus
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export VSC_SOLVER=dv-solve
export VSC_DVSOLVE_XCHECK=1

# Parse the manifest: drop comment (#...) and blank lines.
mapfile -t tests < <(grep -vE '^[[:space:]]*(#|$)' ve/xcheck_corpus.txt)
if [ "${#tests[@]}" -eq 0 ]; then
    echo "ERROR: ve/xcheck_corpus.txt lists no tests" >&2
    exit 1
fi

echo "== dv-solve XCHECK soak: ${#tests[@]} corpus targets =="
printf '   %s\n' "${tests[@]}"
# PYTHON lets a CI venv point at its own interpreter (default: `python`).
PYTHON="${PYTHON:-python}"
exec "$PYTHON" -m pytest --no-cov -q "${tests[@]}" "$@"
