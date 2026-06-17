'''
Bitrot guard for benchmarks/bench_frontends.py: import the harness and run one
warm + cold timing on one workload per available backend (tiny N). Not a perf
gate — just ensures the benchmark's workloads + timing helpers keep working as the
frontends evolve.
'''
import importlib.util
import os

from dc_test_case import DcTestCase
import vsc

_BENCH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "benchmarks", "bench_frontends.py"))


def _load():
    spec = importlib.util.spec_from_file_location("bench_frontends", _BENCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBenchSmoke(DcTestCase):

    def test_workloads_time(self):
        self.assertTrue(os.path.isfile(_BENCH), "benchmark script missing")
        bench = _load()
        self.assertTrue(bench.WORKLOADS)
        for name, classic_cls, dc_cls in bench.WORKLOADS:
            with self.subTest(workload=name):
                # Each scenario builds + (maybe) randomizes on the default backend.
                for cls in (classic_cls, dc_cls):
                    self.assertGreaterEqual(bench.t_per_instance(cls, 2), 0.0)
                    self.assertGreaterEqual(bench.t_reuse(cls, 2), 0.0)
                    self.assertGreaterEqual(bench.t_construct(cls, 2), 0.0)
