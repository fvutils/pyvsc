'''
Distribution-quality comparison: Boolector vs dv-solve.

Scores how *uniform* each back-end's randomization is (chi-square goodness-of-fit
+ coverage), rather than a binary "every value hit?" pass/fail. Run with -s to
see the side-by-side table:

    pytest test_distribution_quality.py -s

Skips dv-solve automatically when the native library is absent.

@author: solver-backend integration
'''
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase
from distribution_score import score


def _available(name):
    try:
        select_backend(name)
        return True
    except Exception:
        return False


BACKENDS = [b for b in ("boolector", "dv-solve") if _available(b)]
N = 5000   # samples per case (V·ln V ≈ 1420 for 256 values → coupon ratio ≈ 3.5)


def _sample(backend, cls, fields, n=N, seed=0):
    """Randomize ``cls`` n times under ``backend``; return {field: [values]}."""
    random.seed(seed)
    ctor.set_solver_backend(backend)
    obj = cls()
    out = {f: [] for f in fields}
    for _ in range(n):
        obj.randomize()
        for f in fields:
            out[f].append(int(getattr(obj, f)))
    return out


class TestDistributionQuality(VscTestCase):

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    # Each case: (title, class factory, {field: feasible-values}).
    def _cases(self):
        cases = []

        @vsc.randobj
        class Unconstrained(object):
            def __init__(s):
                s.k = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.k >= 0
        cases.append(("uint8 unconstrained", lambda: Unconstrained(),
                      {"k": range(0, 256)}))

        @vsc.randobj
        class Relational(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t(); s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a < s.b
        cases.append(("a < b (uint8)", lambda: Relational(),
                      {"a": range(0, 255), "b": range(1, 256)}))

        @vsc.randobj
        class DiscreteSet(object):
            def __init__(s):
                s.k = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.k.inside(vsc.rangelist(0, 64, 128, 192, 255))
        cases.append(("inside {0,64,128,192,255}", lambda: DiscreteSet(),
                      {"k": [0, 64, 128, 192, 255]}))

        @vsc.randobj
        class Ranges(object):
            def __init__(s):
                s.k = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.k.inside(vsc.rangelist(vsc.rng(10, 30), vsc.rng(200, 220)))
        cases.append(("inside [10:30],[200:220]", lambda: Ranges(),
                      {"k": list(range(10, 31)) + list(range(200, 221))}))

        return cases

    def test_distribution_report(self):
        print("\n\n=== Distribution quality: reduced chi-square (≈1.0 ideal), "
              "p-value, coverage ===")
        print("    (lower reduced-chi2 = more uniform; p>0.01 ~ consistent with "
              "uniform)\n")
        worst = []
        for title, factory, field_domains in self._cases():
            print("• %s" % title)
            per_backend = {}
            for backend in BACKENDS:
                samples = _sample(backend, factory, list(field_domains.keys()))
                for f, feasible in field_domains.items():
                    sc = score(samples[f], feasible)
                    per_backend.setdefault(f, {})[backend] = sc
                    print("    %-9s %-3s %s" % (backend, f, sc))
            # Record dv-solve vs boolector for the assertion phase.
            if "dv-solve" in BACKENDS and "boolector" in BACKENDS:
                for f, by_be in per_backend.items():
                    worst.append((title, f, by_be["boolector"], by_be["dv-solve"]))
            print("")

        if not worst:
            self.skipTest("need both back-ends to compare")

        # Quality bar for dv-solve, judged relative to Boolector (the reference)
        # plus absolute floors. These are deliberately lenient — the point is to
        # catch a *materially* worse distribution, not tiny statistical noise.
        for title, f, btor, dvs in worst:
            self.assertGreaterEqual(
                dvs.coverage, 0.99,
                "[%s/%s] dv-solve coverage %.1f%% too low" % (title, f, 100 * dvs.coverage))
            # dv-solve's reduced chi-square should be in the same ballpark as
            # Boolector's (within 3×) and not wildly non-uniform.
            bound = max(2.0, 3.0 * btor.reduced_chi2)
            self.assertLess(
                dvs.reduced_chi2, bound,
                "[%s/%s] dv-solve reduced_chi2 %.2f >> boolector %.2f"
                % (title, f, dvs.reduced_chi2, btor.reduced_chi2))


if __name__ == "__main__":
    unittest.main()
