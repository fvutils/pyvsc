"""Run gpr_variants by name, then check that changing the register set between
calls invalidates the cached plan.

This began as a what-if patch for V6 (snapshot a rangelist over a non-rand
list); the fix is now in randomizer._array_snap, so the patch is gone.
"""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(__file__))
import gpr_variants as g
R = g.RESERVED_RD + g.CFG_RESERVED
for v in sys.argv[1:]:
    g.bench(v, 50, g.AVAIL, R, check=False)
    r = g.bench(v, 2000, g.AVAIL, R)
    print(v, f"{r['us']:.1f} us  bad={r['bad']} err={r['err']}")
# value change between calls must invalidate: alternate two avail sets
A2 = [g.reg.S2, g.reg.S4, g.reg.S6, g.reg.A2, g.reg.A4, g.reg.A6, g.reg.T3, g.reg.T5, g.reg.S8, g.reg.S10]
bad = 0
for k in range(400):
    av = g.AVAIL if k % 2 else A2
    i = g.run_B2(av, R)
    bad += not g.legal(i, av, R)
print("alternating avail sets, violations:", bad)
