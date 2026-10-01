"""Solution-quality comparison for the constrainedrandom study.

Throughput is only half the story: a randomizer that is fast because it
samples-and-retries explores the solution space differently from one that
asks a solver for a uniform witness. This script measures *what* each
configuration produces, not how fast.

Three probes:

  1. `basic`  -- distribution of `a` under `a < b` (8-bit). Under SystemVerilog
     semantics the joint solution space is uniform, so P(a) is proportional to
     (255 - a): strongly decreasing. Sampling `a` uniformly and retrying `b`
     gives a flat P(a) instead. Neither is "wrong", but they cover different
     things.
  2. `alu`    -- coverage of the `a inside {1,2,[100:200]}` value set.
  3. `tight`  -- can the configuration solve a narrow-feasible-region problem
     at all, and if constrainedrandom is given a hand-computed domain, does it
     then succeed?

Run: PYTHONPATH=src:benchmarks python benchmarks/bench_cr_quality.py [N]
"""
import collections
import random
import sys

import vsc
from constrainedrandom import RandObj, RandomizationError

import _cr_workloads as W


def sample(make, n, field, backend=None):
    if backend:
        vsc.set_solver_backend(backend)
    try:
        random.seed(1)
        obj = make()
        out = []
        for _ in range(n):
            obj.randomize()
            r = W.extract_one(obj, field)
            out.append(r)
        return out
    finally:
        if backend:
            vsc.set_solver_backend(None)


def summarize(name, vals, lo, hi, nbuckets=8):
    """Bucket vals over [lo,hi] and print the shape of the distribution."""
    width = (hi - lo + 1) / nbuckets
    buckets = [0] * nbuckets
    for v in vals:
        idx = min(nbuckets - 1, int((v - lo) / width))
        buckets[idx] += 1
    n = len(vals)
    bar = " ".join("%4.1f%%" % (100.0 * b / n) for b in buckets)
    print("  %-10s mean=%8.1f  %s" % (name, sum(vals) / n, bar))


def probe_basic(n):
    print("\n## Probe 1: distribution of `a` given `a < b`, both 8-bit")
    print("   Uniform-over-solutions gives P(a) ~ (255-a): front-loaded, mean ~85.")
    print("   Uniform-over-`a` then retry gives a flat P(a): mean ~127.")
    print("   buckets over a in [0,255], 8 equal buckets:\n")
    summarize("cr", sample(W.cr_basic, n, 'a'), 0, 255)
    summarize("vsc/btor", sample(W.vsc_basic, n, 'a', "boolector"), 0, 255)
    summarize("vdc/dvs", sample(W.vdc_basic, n, 'a', "dv-solve"), 0, 255)


def probe_alu(n):
    print("\n## Probe 2: coverage of `a inside {1, 2, [100:200]}` (103 legal values)")
    print("   distinct values hit out of 103, over %d samples:\n" % n)
    for label, make, be in (("cr", W.cr_alu, None),
                            ("vsc/btor", W.vsc_alu, "boolector"),
                            ("vdc/dvs", W.vdc_alu, "dv-solve")):
        vals = sample(make, n, 'a', be)
        c = collections.Counter(vals)
        print("  %-10s distinct=%3d/103  min_count=%3d  max_count=%3d"
              % (label, len(c), min(c.values()), max(c.values())))


class cr_tight_tuned(RandObj):
    """constrainedrandom CAN do the `tight` problem -- but only if the user
    computes the feasible set by hand and hands it over as a domain. At that
    point the library is not solving the constraint, the user is."""

    def __init__(self):
        super().__init__()
        self.add_rand_var('base', domain=[0x8000_0000])
        self.add_rand_var('addr', domain=range(0x8000_0000, 0x8000_1000, 64))


def probe_tight(n):
    print("\n## Probe 3: `tight` -- narrow feasible region in a 32-bit domain")
    print("   addr in [0x80000000, 0x80001000), addr %% 64 == 0  (64 solutions)\n")
    for label, make, be in (("cr (declared)", W.cr_tight, None),
                            ("cr (hand-tuned domain)", cr_tight_tuned, None),
                            ("vsc/btor", W.vsc_tight, "boolector"),
                            ("vdc/dvs", W.vdc_tight, "dv-solve")):
        try:
            vals = sample(make, n, 'addr', be)
            c = collections.Counter(vals)
            print("  %-24s OK   distinct=%2d/64" % (label, len(c)))
        except RandomizationError:
            print("  %-24s FAILS (RandomizationError: gave up after 100 retries)"
                  % label)
        except Exception as e:                  # noqa: BLE001
            print("  %-24s %s: %s" % (label, type(e).__name__, str(e)[:60]))


def probe_dist(n):
    print("\n## Probe 4: weighted-distribution fidelity")
    print("   declared: 0 -> 10%%, 1..3 -> 80%%, 4 -> 10%%")
    print("   realized bucket shares over %d samples:\n" % n)
    for label, make, be in (("cr", W.cr_dist, None),
                            ("vsc/btor", W.vsc_dist, "boolector"),
                            ("vdc/dvs", W.vdc_dist, "dv-solve")):
        vals = sample(make, n, 'k', be)
        c = collections.Counter(vals)
        b0 = 100.0 * c[0] / n
        b1 = 100.0 * sum(c[v] for v in (1, 2, 3)) / n
        b4 = 100.0 * c[4] / n
        print("  %-10s 0:%5.1f%%   1..3:%5.1f%%   4:%5.1f%%   "
              "(within 1..3: %s)"
              % (label, b0, b1, b4,
                 " ".join("%d=%4.1f%%" % (v, 100.0 * c[v] / n) for v in (1, 2, 3))))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    print("# Solution-quality probes (N=%d per configuration)" % n)
    probe_basic(n)
    probe_alu(n)
    probe_tight(min(n, 500))
    probe_dist(n)


if __name__ == "__main__":
    main()
