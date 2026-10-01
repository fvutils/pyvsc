"""Isolates WHICH constraint shape collapses the dv-solve solution distribution.

Finding: a plain range samples fine; adding any alignment/divisibility term
(`% 64 == 0` or `& 0x3F == 0`) collapses dv-solve onto the range's lowest legal
value ~93% of the time. See benchmarks/RESULTS_constrainedrandom.md section 3.

Run: PYTHONPATH=src python benchmarks/bench_cr_distshape.py
"""
import collections

import vsc
import vsc.dc as vdc


@vdc.dataclass
class A_plain(vdc.RandClass):
    """plain range only"""
    addr: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.addr >= 0x8000_0000
        self.addr < 0x8000_1000


@vdc.dataclass
class B_mod(vdc.RandClass):
    """range + modulo alignment"""
    addr: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.addr >= 0x8000_0000
        self.addr < 0x8000_1000
        self.addr % 64 == 0


@vdc.dataclass
class C_mask(vdc.RandClass):
    """range + bitmask alignment"""
    addr: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.addr >= 0x8000_0000
        self.addr < 0x8000_1000
        (self.addr & 0x3F) == 0


@vdc.dataclass
class D_relational(vdc.RandClass):
    """range expressed against another rand var (the benchmark's shape)"""
    addr: vdc.u32 = vdc.rand()
    base: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.base == 0x8000_0000
        self.addr >= self.base
        self.addr < self.base + 0x1000
        (self.addr & 0xFFF) % 64 == 0


def run(C, be, n=4000):
    vsc.set_solver_backend(be)
    try:
        o = C()
        vals = []
        for _ in range(n):
            o.randomize()
            vals.append(int(o.addr))
        c = collections.Counter(vals)
        cnt = sorted(c.values())
        top = c.most_common(1)[0]
        return "distinct=%5d  max_share=%5.1f%%  (top value %#x)" % (
            len(c), 100.0 * top[1] / n, top[0])
    finally:
        vsc.set_solver_backend(None)


for C in (A_plain, B_mod, C_mask, D_relational):
    print("%-14s %-9s %s" % (C.__name__, "dv-solve", run(C, "dv-solve")))
    print("%-14s %-9s %s" % ("", "boolector", run(C, "boolector")))
    print()
