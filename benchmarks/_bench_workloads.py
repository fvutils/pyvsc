"""Diverse dataclass workloads for the optimization comparison
(benchmarks/bench_optimizations.py). Dataclass front-end so structure is shared
per type (the create-many pattern) and constraint source is importable."""
import vsc.dc as vdc


@vdc.dataclass
class Scalar(vdc.RandClass):
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


@vdc.dataclass
class Alu(vdc.RandClass):
    op: vdc.u4 = vdc.rand()
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.op <= 7
        self.a < self.b
        self.a.inside(vdc.rangelist(1, 2, (100, 200)))


@vdc.dataclass
class Wide(vdc.RandClass):
    x: vdc.u64 = vdc.rand()
    y: vdc.u64 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.x < self.y
        self.x > 1000


@vdc.dataclass
class Dist(vdc.RandClass):
    k: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.dist(self.k, [vdc.weight(0, 10), vdc.weight((1, 3), 80), vdc.weight(4, 10)])


@vdc.dataclass
class Sub(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()


@vdc.dataclass
class Nested(vdc.RandClass):
    s1: Sub = vdc.rand()
    s2: Sub = vdc.rand()

    @vdc.constraint
    def c(self):
        self.s1.a == self.s2.a


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


Arr8 = _arr(8)
Arr32 = _arr(32)
Arr128 = _arr(128)
Arr256 = _arr(256)
Arr512 = _arr(512)


@vdc.dataclass
class Packet(vdc.RandClass):
    """A realistic mixed sequence-item: a few constrained scalars + a data array."""
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


WORKLOADS = [
    ("scalar", Scalar), ("alu", Alu), ("wide64", Wide), ("dist", Dist),
    ("nested", Nested), ("packet16", Packet),
    ("arr8", Arr8), ("arr32", Arr32), ("arr128", Arr128),
    ("arr256", Arr256), ("arr512", Arr512),
]
