"""Ways to express pygen's randomize_gpr constraints in vdc.

pygen (classic):
    with instr.randomize_with():
        if avail_regs.size > 0:
            if has_rs1: rs1 in avail_regs   (same rs2, rd)
        foreach reserved_rd:   if has_rd: rd != reserved_rd[i];  if CB: rs1 != reserved_rd[i]
        foreach cfg.reserved_regs: same

Each variant: fresh instruction per randomize (pygen's pattern), N draws, check
legality, report us/randomize.
"""
import os, random, sys, time
from enum import IntEnum
import vsc
import vsc.dc as vdc

if os.environ.get("BE", "dv-solve") == "dv-solve":
    vsc.set_solver_backend("dv-solve")


class reg(IntEnum):
    ZERO = 0; RA = 1; SP = 2; GP = 3; TP = 4; T0 = 5; T1 = 6; T2 = 7
    S0 = 8; S1 = 9; A0 = 10; A1 = 11; A2 = 12; A3 = 13; A4 = 14; A5 = 15
    A6 = 16; A7 = 17; S2 = 18; S3 = 19; S4 = 20; S5 = 21; S6 = 22; S7 = 23
    S8 = 24; S9 = 25; S10 = 26; S11 = 27; T3 = 28; T4 = 29; T5 = 30; T6 = 31


# stream state (what riscv_rand_instr_stream holds)
AVAIL = [reg.S0, reg.A1, reg.T2, reg.A5, reg.S3, reg.T4, reg.A0, reg.S1, reg.T6, reg.A3]
RESERVED_RD = [reg.A1]
CFG_RESERVED = [reg.TP, reg.SP, reg.T2]   # tp, sp, scratch -- as pygen's cfg does


def legal(i, avail, reserved):
    ok = True
    for f in ("rs1", "rs2", "rd"):
        ok &= getattr(i, f) in avail
    ok &= i.rd not in reserved
    return ok


# ---------------------------------------------------------------- A: inline
@vdc.dataclass
class InstrA(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()


def run_A(avail, reserved):
    i = InstrA()
    with i.randomize_with() as it:
        it.rs1.inside(vdc.rangelist(*avail))
        it.rs2.inside(vdc.rangelist(*avail))
        it.rd.inside(vdc.rangelist(*avail))
        for r in reserved:
            it.rd != r
    return i


# ---------------------------------------------------- B: non-rand list fields
@vdc.dataclass
class InstrB(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()
    avail: list[reg] = vdc.field(default_factory=list)
    reserved: list[reg] = vdc.field(default_factory=list)

    @vdc.constraint
    def gpr_c(self):
        self.rs1.inside(vdc.rangelist(self.avail))
        self.rs2.inside(vdc.rangelist(self.avail))
        self.rd.inside(vdc.rangelist(self.avail))
        with vdc.foreach(self.reserved, idx=True) as k:
            self.rd != self.reserved[k]


def run_B(avail, reserved):
    i = InstrB(avail=list(avail), reserved=list(reserved))
    i.randomize()
    return i


# ------------------------------------- C: instruction refers to its stream object
@vdc.dataclass
class Stream(vdc.RandClass):
    avail_regs: list[reg] = vdc.field(default_factory=list)
    reserved: list[reg] = vdc.field(default_factory=list)


@vdc.dataclass
class InstrC(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()
    stream: Stream = vdc.field()

    @vdc.constraint
    def gpr_c(self):
        self.rs1.inside(vdc.rangelist(self.stream.avail_regs))
        self.rs2.inside(vdc.rangelist(self.stream.avail_regs))
        self.rd.inside(vdc.rangelist(self.stream.avail_regs))
        with vdc.foreach(self.stream.reserved, idx=True) as k:
            self.rd != self.stream.reserved[k]


_STREAM = {}


def run_C(avail, reserved):
    key = (tuple(avail), tuple(reserved))
    s = _STREAM.get(key)
    if s is None:
        s = _STREAM[key] = Stream(avail_regs=list(avail), reserved=list(reserved))
    i = InstrC(stream=s)
    i.randomize()
    return i


# ----------------------------------------------- D: no gpr constraint (floor)
def run_D(avail, reserved):
    i = InstrA()
    i.randomize()
    return i


VARIANTS = dict(A=run_A, B=run_B, C=run_C, D=run_D)


def bench(name, n, avail, reserved, check=True):
    fn = VARIANTS[name]
    bad = 0
    err = None
    t0 = time.perf_counter()
    try:
        for _ in range(n):
            i = fn(avail, reserved)
            if check and not legal(i, avail, reserved):
                bad += 1
    except Exception as e:  # noqa
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    return dict(us=1e6 * dt / n, bad=bad, err=err)


def _main():
    random.seed(1)
    n = int(os.environ.get("N", "2000"))
    reserved = RESERVED_RD + CFG_RESERVED
    for name in sys.argv[1:] or VARIANTS:
        bench(name, 50, AVAIL, reserved, check=False)  # warm
        r = bench(name, n, AVAIL, reserved, check=(name not in ("D",)))
        print(f"{name}: {r['us']:8.1f} us/randomize  violations={r['bad']}  err={r['err']}")


# ------------------- B2: like B but class default has the instance's lengths
@vdc.dataclass
class InstrB2(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()
    avail: list[reg] = vdc.field(default_factory=lambda: list(AVAIL))
    reserved: list[reg] = vdc.field(default_factory=lambda: RESERVED_RD + CFG_RESERVED)

    @vdc.constraint
    def gpr_c(self):
        self.rs1.inside(vdc.rangelist(self.avail))
        self.rs2.inside(vdc.rangelist(self.avail))
        self.rd.inside(vdc.rangelist(self.avail))
        with vdc.foreach(self.reserved, idx=True) as k:
            self.rd != self.reserved[k]


def run_B2(avail, reserved):
    i = InstrB2(avail=list(avail), reserved=list(reserved))
    i.randomize()
    return i


# ------------- E: same sets as literal constants in the class (structure floor)
@vdc.dataclass
class InstrE(vdc.RandClass):
    rs1: reg = vdc.rand()
    rs2: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u32 = vdc.rand()

    @vdc.constraint
    def gpr_c(self):
        self.rs1.inside(vdc.rangelist(reg.S0, reg.A1, reg.T2, reg.A5, reg.S3, reg.T4, reg.A0, reg.S1, reg.T6, reg.A3))
        self.rs2.inside(vdc.rangelist(reg.S0, reg.A1, reg.T2, reg.A5, reg.S3, reg.T4, reg.A0, reg.S1, reg.T6, reg.A3))
        self.rd.inside(vdc.rangelist(reg.S0, reg.A5, reg.S3, reg.T4, reg.A0, reg.S1, reg.T6, reg.A3))


def run_E(avail, reserved):
    i = InstrE()
    i.randomize()
    return i


# --------------- F: E's sets on plain u8 fields (is the enum excluded from T0?)
_RS = [int(r) for r in AVAIL]
@vdc.dataclass
class InstrF(vdc.RandClass):
    rs1: vdc.u8 = vdc.rand()
    rs2: vdc.u8 = vdc.rand()
    rd: vdc.u8 = vdc.rand()
    imm: vdc.u32 = vdc.rand()

    @vdc.constraint
    def gpr_c(self):
        self.rs1.inside(vdc.rangelist(8, 11, 7, 15, 19, 29, 10, 9, 31, 13))
        self.rs2.inside(vdc.rangelist(8, 11, 7, 15, 19, 29, 10, 9, 31, 13))
        self.rd.inside(vdc.rangelist(8, 15, 19, 29, 10, 9, 31, 13))


def run_F(avail, reserved):
    i = InstrF()
    i.randomize()
    return i


VARIANTS.update(B2=run_B2, E=run_E, F=run_F)

if __name__ == "__main__":
    _main()
