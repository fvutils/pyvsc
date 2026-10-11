#!/bin/bash
# Run the last release's own unit tests (ve/unit as tagged, unmodified)
# against the current src/, once per solver back-end.
#
#   ve/run_release_compat.sh [tag]      # default: latest tag on master
#
# Guards against breaking existing users: a test the release shipped with
# must still pass on the code we are about to publish.
set -e -o pipefail
root=$(cd $(dirname $0)/.. && pwd)
tag=${1:-$(git -C $root describe --tags --abbrev=0 master)}
py=${PYTHON:-$root/packages/python/bin/python}
work=$(mktemp -d)
trap "rm -rf $work" EXIT

git -C $root archive $tag ve/unit | tar -x -C $work
echo "Running $tag ve/unit against $root/src"
status=0
for solver in boolector dv-solve; do
    echo "== VSC_SOLVER=$solver"
    (cd $work/ve/unit && PYTHONPATH=$root/src VSC_SOLVER=$solver \
        $py -m pytest -q -p no:cacheprovider test_*.py) | tail -1 || status=1
done
exit $status
