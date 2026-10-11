"""Per-call cost of randomize() / randomize_with() on a riscv-dv-like
instruction (doc/notes/pyvsc_inline_hot_path_plan.md).

    PYTHONPATH=src packages/python/bin/python benchmarks/riscv_dv_vdc/inline_cost.py [prof CASE]

CASE is one of the case names printed; `prof` runs it under cProfile.
"""
import cProfile
import pstats
import random
import sys
import timeit
from enum import IntEnum

import vsc
import vsc.dc as vdc

vsc.set_solver_backend("dv-solve")


class reg(IntEnum):
    ZERO = 0; RA = 1; SP = 2; GP = 3; TP = 4; T0 = 5; T1 = 6; T2 = 7
    S0 = 8; S1 = 9; A0 = 10; A1 = 11; A2 = 12; A3 = 13; A4 = 14; A5 = 15
    A6 = 16; A7 = 17; S2 = 18; S3 = 19; S4 = 20; S5 = 21; S6 = 22; S7 = 23


@vdc.dataclass
class Instr(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()


i = Instr()
rng = random.Random(1)
SETS = [rng.sample(list(reg), 10) for _ in range(64)]
k = [0]


def plain():
    i.randomize()


def one_ne():
    with i.randomize_with() as it:
        it.rd != reg.SP


def _gpr(av):
    with i.randomize_with() as it:
        it.rs1.inside(vdc.rangelist(*av))
        it.rs2.inside(vdc.rangelist(*av))
        it.rd.inside(vdc.rangelist(*av))
        it.rd != reg.SP
        it.rd != reg.TP


def gpr_hit():
    _gpr(SETS[0])


def gpr_miss():
    k[0] += 1
    _gpr(SETS[k[0] % len(SETS)])


CASES = [("plain", plain, 50000), ("one_ne", one_ne, 50000),
         ("gpr_hit", gpr_hit, 10000), ("gpr_miss", gpr_miss, 3000)]

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "prof":
        name = sys.argv[2]
        f, n = [(f, n) for c, f, n in CASES if c == name][0]
        f()
        pr = cProfile.Profile()
        pr.enable()
        for _ in range(n):
            f()
        pr.disable()
        pstats.Stats(pr).sort_stats("tottime").print_stats(40)
    else:
        for name, f, n in CASES:
            f()
            best = min(timeit.repeat(f, number=n, repeat=3)) / n * 1e6
            print("%-10s %8.2f us" % (name, best))
