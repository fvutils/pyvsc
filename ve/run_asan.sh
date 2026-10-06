#!/usr/bin/env bash
#
# Run the test suite against an AddressSanitizer-instrumented dv-solve, to catch
# native memory bugs (out-of-bounds, use-after-free, wild pointers) that stay
# latent in a normal build but crash under a different heap layout — e.g. the CI
# environment -- e.g. the unwired-ctypes pointer truncation (builder_expr_concat
# with no argtypes) that crashed CI and that a normal local build hid.
#
# Usage:
#   ve/run_asan.sh                      # CI's ve/unit slice (the default target)
#   ve/run_asan.sh ve/unit/test_x.py    # specific file(s) / node ids
#   ve/run_asan.sh -k wide -x           # extra pytest args pass straight through
#   ve/run_asan.sh --dc                 # the dataclass suite (ve/unit_dc) instead
#   REBUILD=1 ve/run_asan.sh ...        # force a rebuild of the ASAN lib
#
# Env knobs: PYTHON (python to use), REBUILD=1 (rebuild the instrumented lib).
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DVS="$ROOT/packages/dv-solve"
BUILD="$DVS/build-asan"
PYTHON="${PYTHON:-python}"

# --- locate the ASAN runtime the compiler ships (must be LD_PRELOADed so a
#     dlopen'd instrumented .so initialises correctly) ------------------------
ASANLIB="$(gcc -print-file-name=libasan.so 2>/dev/null)"
if [ ! -e "$ASANLIB" ]; then
    ASANLIB="$(clang -print-file-name=libclang_rt.asan-x86_64.so 2>/dev/null)"
fi
if [ ! -e "$ASANLIB" ]; then
    echo "error: could not find an ASan runtime (libasan.so). Install gcc/clang." >&2
    exit 1
fi

# --- build the instrumented lib on demand (Debug build type turns on
#     -fsanitize=address; see packages/dv-solve/CMakeLists.txt) ---------------
if [ "${REBUILD:-0}" = "1" ] || [ ! -e "$BUILD/libdv_solve.so" ]; then
    echo ">> building ASAN dv-solve in $BUILD ..."
    mkdir -p "$BUILD"
    ( cd "$BUILD" \
        && cmake -DCMAKE_BUILD_TYPE=Debug -DDV_SOLVE_BUILD_TOOLS=OFF .. \
        && make dv_solve -j"$(nproc)" ) || {
        echo "error: ASAN build failed" >&2; exit 1; }
fi

# --- pick the target set: --dc -> dataclass suite; passthrough paths/args ----
DC=0
ARGS=()
for a in "$@"; do
    if [ "$a" = "--dc" ]; then DC=1; else ARGS+=("$a"); fi
done
if [ "${#ARGS[@]}" -eq 0 ]; then
    if [ "$DC" = "1" ]; then
        ARGS=(ve/unit_dc)
    else
        # The exact slice CI runs (see .github/workflows/ci.yml).
        mapfile -t ARGS < <(ls "$ROOT"/ve/unit/*.py \
            | grep -v test_random_dist \
            | grep -v vsc_test_case \
            | grep -v test_covergroup_programmatic \
            | grep -v test_rand_mode)
    fi
fi

echo ">> ASan runtime : $ASANLIB"
echo ">> ASan lib     : $BUILD/libdv_solve.so"
echo ">> targets      : ${#ARGS[@]} item(s)"

# ZSP_SOLVER_PATH is a DIRECTORY the loader searches (not a file). Disable
# pytest's faulthandler so ASan — not faulthandler — reports the C-level stack
# on a fault. Defaults (override via a pre-set ASAN_OPTIONS):
#   detect_leaks=0            the Python interpreter leaks by design
#   alloc_dealloc_mismatch=0  Python mixes allocators across the C boundary; this
#                             is benign here and would otherwise be a false abort
export ASAN_OPTIONS="${ASAN_OPTIONS:-detect_leaks=0:abort_on_error=1:print_stacktrace=1:alloc_dealloc_mismatch=0}"
cd "$ROOT"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
LD_PRELOAD="$ASANLIB" \
ZSP_SOLVER_PATH="$BUILD" \
VSC_SOLVER=dv-solve \
    "$PYTHON" -m pytest --no-cov -p no:faulthandler -p no:cacheprovider -q "${ARGS[@]}"
rc=$?

if [ "$rc" -eq 0 ]; then
    echo ">> ASAN run clean (exit 0)"
else
    echo ">> ASAN run FAILED (exit $rc) — scroll up for the AddressSanitizer report" >&2
fi
exit "$rc"
