"""pyvsc performance harness and committed history.

Design: doc/notes/pyvsc_benchmark_suite_design.md. Run from the repo root:

    PYTHONPATH=benchmarks python3 -m perf.collect --kind manual --suites core
    PYTHONPATH=benchmarks python3 -m perf.consolidate build/perf/runs/<record>.json.gz
    PYTHONPATH=benchmarks python3 -m perf.render --out doc/source/results

The harness is imported from the working tree. The code under test is not:
each measured cell runs in a child process whose PYTHONPATH points at that
arm's build (perf.arms), so the same harness can measure pyvsc 0.9.5 and
constrainedrandom beside the working tree.
"""
