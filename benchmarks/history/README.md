# Committed performance history

Written only by `python3 -m perf.consolidate` (run with `PYTHONPATH=benchmarks`);
never edited by hand. The harness is `benchmarks/perf/`; the pages rendered from
these files are published with the docs at https://dvkit.org/fvutils/pyvsc/results/.

| Path | Content |
|---|---|
| `<year>.jsonl` | One trend line per run, sorted by `utc`: the CPU µs per call of every (workload, pattern, arm) cell, in manifest order, plus provenance (pyvsc and dv-solve commits, versions, Python, machine, calibration). Plain text on purpose: git delta-compresses appended text, and a gzipped file would cost its full size on every change. |
| `manifests/<hash>.json` | A resolved suite: the workloads (with family, rev and source hash), arms, patterns and measurement protocol that give a trend line's arrays their meaning. |
| `machines/<id>.json` | Each machine class runs were measured on: CPU model, cores, memory, kernel. Never a host name. The id is derived as in dv-solve, so a machine has the same id in both histories. |
| `releases/<tag>.json.gz` | The full run record of each release's perf run (the earliest valid one). Written once. |

Every other run's full record is a build artifact (`perf-<kind>-<utc>-<sha>`),
which expires. Consolidate before then: at each release, and at least monthly.
Invalid, noisy and dirty runs get a line too, flagged, so the history records
that a run was bad rather than silently lacking it.
