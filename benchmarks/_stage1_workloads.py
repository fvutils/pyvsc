"""Workload set for the Stage 1 overhead-removal ladder
(doc/notes/vdc_stage1_impl_plan.md).

Deliberately narrower than `_bench_workloads.WORKLOADS`: one representative per
*shape that Stage 1 can affect*, plus the three feature shapes whose
housekeeping walks S1.4 proposes to make pay-per-use (soft, hooks, randc). A
Stage 1 step that speeds up `arr128` while regressing `soft` or `hooks` has to
be visible here, not in a geo-mean.
"""
import vsc.dc as vdc


@vdc.dataclass
class Basic(vdc.RandClass):
    """Two constrained scalars — the small-problem case, where the fixed
    per-randomize cost dominates completely."""
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


def _arr(n):
    @vdc.dataclass
    class A(vdc.RandClass):
        arr: list[vdc.u8] = vdc.rand(size=n)

        @vdc.constraint
        def c(self):
            with vdc.foreach(self.arr) as it:
                it > 2
                it < 250
    A.__name__ = "Arr%d" % n
    return A


Arr32 = _arr(32)
Arr128 = _arr(128)


@vdc.dataclass
class _Sub(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()


@vdc.dataclass
class Nested(vdc.RandClass):
    """Composite children — the walks S1.4 targets recurse through these, and
    S1.3's copy-in list has to handle them."""
    s1: _Sub = vdc.rand()
    s2: _Sub = vdc.rand()

    @vdc.constraint
    def c(self):
        self.s1.a == self.s2.a
        self.s1.b < self.s2.b


@vdc.dataclass
class Soft(vdc.RandClass):
    """has_soft=True — must not be affected by the C1 soft-priority skip."""
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.soft(self.a == 100)
        self.b > self.a


@vdc.dataclass
class Randc(vdc.RandClass):
    """randc cycling — exercises the cyclic path, which reads field values
    between solves and so is sensitive to S1.3's copy-in skip."""
    k: vdc.u4 = vdc.randc()

    @vdc.constraint
    def c(self):
        self.k < 12


@vdc.dataclass
class Hooks(vdc.RandClass):
    """has_user_hooks=True — the C3 walk must still fire here, and writeback
    must still land before the hook runs.

    The hook writes a *plain* attribute, not a dataclass field: writing a
    non-rand field invalidates the Tier-A plan cache, which is what `Knob`
    below measures. Keeping the two apart is deliberate — otherwise this
    workload reports plan-cache misses as hook cost."""
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b

    def post_randomize(self):
        # reads a solved value: proves writeback-before-hook ordering
        self._seen = self.a


@vdc.dataclass
class Knob(vdc.RandClass):
    """The config/knob pattern: a non-rand field mutated between solves.

    `seen` is referenced by no constraint, so its value cannot affect the
    solution — but the Tier-A plan cache's freshness signature snapshots
    *every* non-used-rand field, so writing it invalidates the plan on every
    solve. Measured cliff: 91 195 -> 11 982 solves/sec (7.6x). See S1.7."""
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()
    seen: vdc.u32 = vdc.field(default=0)

    @vdc.constraint
    def c(self):
        self.a < self.b

    def post_randomize(self):
        self.seen = self.a


@vdc.dataclass
class Packet(vdc.RandClass):
    """A realistic mixed sequence item — the shape users actually write."""
    kind: vdc.u4 = vdc.rand()
    addr: vdc.u32 = vdc.rand()
    length: vdc.u8 = vdc.rand()
    payload: list[vdc.u8] = vdc.rand(size=16)

    @vdc.constraint
    def c(self):
        self.kind <= 7
        self.addr > 0x1000
        self.length.inside(vdc.rangelist((1, 16)))
        with vdc.foreach(self.payload) as b:
            b != 0


# (name, cls, warm-iteration count).  Counts are chosen so every workload takes
# roughly the same wall-clock at scale=1.
WORKLOADS = [
    ("basic",    Basic,   3000),
    ("nested",   Nested,  3000),
    ("soft",     Soft,    2000),
    ("randc",    Randc,   3000),
    ("hooks",    Hooks,   3000),
    ("knob",     Knob,    2000),
    ("packet16", Packet,  1500),
    ("arr32",    Arr32,   1200),
    ("arr128",   Arr128,   400),
]

#: The workload Stage 1's headline target is stated against.
TARGET_WORKLOAD = "arr128"
TARGET_SPS = 13000
