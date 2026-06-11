"""Ad-hoc scorer comparison: BV-SAT XOR sampler vs Boolector on the wide-var
cases that route to dv-solve's BV-SAT SAT-serving path.

Not a pytest test — a manual measurement harness (plan §2.5). Run:

    VSC_DVSOLVE_BVSAT_SERVE_SAT=1 python _sampler_scoring.py
"""
import random
import sys

import vsc
from vsc.impl import ctor
from distribution_score import score


def _sample(backend, factory, fields, n, seed=0):
    random.seed(seed)
    ctor.set_solver_backend(backend)
    obj = factory()
    out = {f: [] for f in fields}
    for _ in range(n):
        obj.randomize()
        for f in fields:
            out[f].append(int(getattr(obj, f)))
    ctor.set_solver_backend(None)
    return out


def _cases():
    cases = []

    @vsc.randobj
    class WideSmallSet(object):
        def __init__(s):
            s.b = vsc.rand_uint64_t()
        @vsc.constraint
        def c(s):
            s.b.inside(vsc.rangelist(*range(0, 20)))
    cases.append(("uint64 inside {0..19}", lambda: WideSmallSet(),
                  {"b": list(range(0, 20))}))

    @vsc.randobj
    class WideRange(object):
        def __init__(s):
            s.r = vsc.rand_uint64_t()
        @vsc.constraint
        def cc(s):
            s.r.inside(vsc.rangelist(vsc.rng(0, 99)))
    cases.append(("uint64 inside [0:99]", lambda: WideRange(),
                  {"r": list(range(0, 100))}))

    @vsc.randobj
    class WideGapped(object):
        def __init__(s):
            s.d = vsc.rand_uint64_t()
        @vsc.constraint
        def c(s):
            s.d.inside(vsc.rangelist(vsc.rng(0, 9), vsc.rng(1000, 1009)))
    cases.append(("uint64 inside [0:9],[1000:1009]", lambda: WideGapped(),
                  {"d": list(range(0, 10)) + list(range(1000, 1010))}))

    @vsc.randobj
    class WideSigned(object):
        def __init__(s):
            s.e = vsc.rand_int64_t()
        @vsc.constraint
        def c(s):
            s.e.inside(vsc.rangelist(vsc.rng(-7, 7)))
    cases.append(("int64 inside [-7:7]", lambda: WideSigned(),
                  {"e": list(range(-7, 8))}))

    return cases


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    backends = ["boolector", "dv-solve"]
    print("\n=== Sampler scoring (n=%d/case) — reduced_chi2 (~1 ideal), p, coverage ===\n" % n)
    for title, factory, doms in _cases():
        print("• %s" % title)
        for be in backends:
            try:
                s = _sample(be, factory, list(doms.keys()), n)
            except Exception as ex:
                print("    %-9s  ERROR: %s" % (be, ex))
                continue
            for f, feasible in doms.items():
                print("    %-9s %s %s" % (be, f, score(s[f], feasible)))
        print("")


if __name__ == "__main__":
    main()
