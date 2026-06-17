"""dv-solve zero-fallback guard for the benchmark workloads (plan Workstream C2).

The most likely *performance* regression on the dv-solve path is silent: a
workload that used to serve natively starts deferring a RandSet to Boolector
again (a redundant second solve, often a large slowdown — e.g. the Phase-G
wide64/alu losses were exactly this). The throughput benchmark
(`benchmarks/bench_frontends.py`) would show it, but nothing *fails* — so it can
rot unnoticed between manual runs.

This test ties the benchmark workload set to native serving: it runs each of the
six bench workloads (simple, alu, array, wide64, dist, nested) under the always-on
fallback tally and asserts **zero** deferrals. dv-solve "wins on all six" (Phase G)
precisely because it serves them without the Boolector round-trip; if any starts
deferring, this fails loudly and points at the regressed workload. It is the
correctness↔performance tie-in: a silent fallback is both.

Distinct from `test_dvsolve_fallback_histogram.py` (the burn-down dashboard with a
documented residual allowlist over a broader corpus) — this one is narrow and
absolute: the *perf* workloads must never defer, in any reason code.

Skipped when the dv-solve native library is unavailable.
See doc/notes/dv_solve_test_suite_enhancement_plan.md (Workstream C2).
"""
import random
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _tally():
    """Enable the always-on fallback tally for the block, yielding the getter.
    Snapshots/restores the process-global tally so this test's measurement does
    not corrupt a concurrent suite-wide self-sufficiency audit."""
    snap = rnd.snapshot_fallback_tally()
    rnd.set_fallback_tally(True)
    rnd.reset_fallback_tally()
    try:
        yield rnd.get_fallback_tally
    finally:
        rnd.restore_fallback_tally(snap)


# --- the benchmark workloads (mirror benchmarks/bench_frontends.py) --------- #

@vsc.randobj
class C_simple(object):
    def __init__(s):
        s.a = vsc.rand_uint8_t(); s.b = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.a < s.b


@vsc.randobj
class C_alu(object):
    def __init__(s):
        s.op = vsc.rand_bit_t(4); s.a = vsc.rand_uint32_t(); s.b = vsc.rand_uint32_t()

    @vsc.constraint
    def c(s):
        s.op <= 7
        s.a < s.b
        s.a.inside(vsc.rangelist(1, 2, (100, 200)))


@vsc.randobj
class C_array(object):
    def __init__(s):
        s.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

    @vsc.constraint
    def c(s):
        with vsc.foreach(s.arr) as it:
            it > 2
            it < 250


@vsc.randobj
class C_wide(object):
    def __init__(s):
        s.x = vsc.rand_uint64_t(); s.y = vsc.rand_uint64_t()

    @vsc.constraint
    def c(s):
        s.x < s.y
        s.x > 1000


@vsc.randobj
class C_dist(object):
    def __init__(s):
        s.k = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        vsc.dist(s.k, [vsc.weight(0, 10), vsc.weight((1, 3), 80), vsc.weight(4, 10)])


@vsc.randobj
class C_sub(object):
    def __init__(s):
        s.a = vsc.rand_uint16_t(); s.b = vsc.rand_uint16_t()


@vsc.randobj
class C_nested(object):
    def __init__(s):
        s.s1 = vsc.rand_attr(C_sub()); s.s2 = vsc.rand_attr(C_sub())

    @vsc.constraint
    def c(s):
        s.s1.a < s.s1.b


WORKLOADS = [
    ("simple", C_simple), ("alu", C_alu), ("array", C_array),
    ("wide64", C_wide), ("dist", C_dist), ("nested", C_nested),
]


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveZeroFallback(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_bench_workloads_serve_native(self):
        """Each benchmark workload must serve with zero Boolector deferrals — a
        silent fallback is the canonical dv-solve perf regression."""
        offenders = []
        for name, cls in WORKLOADS:
            with _tally() as tally:
                random.seed(0)
                obj = cls()
                for _ in range(100):
                    obj.randomize()
                hist = tally()
            if hist:
                offenders.append("%s -> %s" % (name, hist))
        self.assertEqual(
            offenders, [],
            "perf workload(s) deferred to Boolector (native-serving regression): "
            + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
