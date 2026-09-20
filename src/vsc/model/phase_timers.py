"""Per-phase timing attribution for ``randomize()``.

Opt-in via ``VSC_PHASE_TIMERS=1``, read once at import. When off, ``now()`` and
``add()`` are no-op stubs, so the cost at each instrumentation site is two
function calls (~100ns total per site) — not free, which is why
``benchmarks/bench_stage1.py`` takes its *headline* numbers in a separate
process with the variable unset and uses this only for attribution. See
``doc/notes/vdc_stage1_impl_plan.md`` §S1.1.

Rationale for real timers rather than cProfile: the profiler distorted these
same measurements by up to ~2.5x (``dv_solve_boundary_overhead_findings.md``).

Usage at an instrumentation site::

    _t = PT.now()
    ...work...
    PT.add("apply_node", _t)
"""
import os
import time
from collections import Counter, defaultdict

ENABLED = os.environ.get("VSC_PHASE_TIMERS", "0").lower() not in ("0", "", "false", "no")

#: phase name -> total seconds
acc = defaultdict(float)
#: phase name -> number of intervals recorded
cnt = Counter()

#: Declaration order for reporting (phases not listed are appended, sorted).
ORDER = [
    "apply_node",       # vdc copy-in  (solve_view._apply_node)
    "set_used_rand",    # randomizer housekeeping walk
    "clear_soft_pri",   # randomizer housekeeping walk
    "pre_randomize",    # randomizer housekeeping walk
    "randinfo_build",   # RandSet partitioning (skipped on a plan-cache hit)
    "solve",            # native solve (inside the back-end)
    "readback",         # field values out of the solver
    "rollback",         # constraint-override rollback walk
    "post_randomize",   # randomizer housekeeping walk (drives vdc writeback)
    "writeback",        # vdc model -> instance attributes
]


if ENABLED:
    now = time.perf_counter

    def add(name, t0):
        acc[name] += time.perf_counter() - t0
        cnt[name] += 1
else:
    def now():
        return 0.0

    def add(name, t0):
        pass


def reset():
    acc.clear()
    cnt.clear()


def report(n_solves, total_s=None):
    """Return a list of ``(name, total_us, us_per_solve, pct, calls_per_solve)``.

    ``pct`` is against ``total_s`` if given, else against the sum of phases.
    Phases nest (``solve`` is inside the back-end call), so the sum is *not*
    necessarily the whole of ``randomize()`` — always pass ``total_s``.
    """
    denom = total_s if total_s else sum(acc.values())
    names = [n for n in ORDER if n in acc] + sorted(set(acc) - set(ORDER))
    out = []
    for n in names:
        t = acc[n]
        out.append((n, t * 1e6, t * 1e6 / n_solves,
                    100.0 * t / denom if denom else 0.0,
                    cnt[n] / n_solves))
    if total_s:
        unattributed = total_s - sum(acc.values())
        out.append(("(unattributed)", unattributed * 1e6,
                    unattributed * 1e6 / n_solves,
                    100.0 * unattributed / total_s, 0.0))
    return out
