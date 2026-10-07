"""Composite workloads: sub-objects. constrainedrandom has no composition."""
from . import Workload, workload


@workload
class Nested2(Workload):
    name, family = "nested2", "composite"
    fields = ("s1.a", "s1.b", "s2.a", "s2.b")

    def classic(vsc):
        @vsc.randobj
        class Sub:
            def __init__(self):
                self.a = vsc.rand_uint16_t()
                self.b = vsc.rand_uint16_t()

        @vsc.randobj
        class Nested2:
            def __init__(self):
                self.s1 = vsc.rand_attr(Sub())
                self.s2 = vsc.rand_attr(Sub())

            @vsc.constraint
            def c(self):
                self.s1.a == self.s2.a
        return Nested2

    def dc(vdc):
        @vdc.dataclass
        class Sub(vdc.RandClass):
            a: vdc.u16 = vdc.rand()
            b: vdc.u16 = vdc.rand()

        @vdc.dataclass
        class Nested2(vdc.RandClass):
            s1: Sub = vdc.rand()
            s2: Sub = vdc.rand()

            @vdc.constraint
            def c(self):
                self.s1.a == self.s2.a
        return Nested2

    def check(s):
        return s["s1.a"] == s["s2.a"] and all(0 <= v < 65536 for v in s.values())
