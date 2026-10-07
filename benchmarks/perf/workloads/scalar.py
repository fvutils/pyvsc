"""Scalar workloads: a few constrained fields, no arrays or sub-objects.

No `from __future__ import annotations` here or in any workload module: the
dataclass front-end reads field annotations when the class is created, and
the builders define their classes inside a function, where a string
annotation could not be resolved.
"""
from . import Workload, workload


@workload
class Basic(Workload):
    """constrainedrandom's VSCBasic: four bytes, one ordering constraint."""
    name, family = "basic", "scalar"
    fields = ("a", "b", "c", "d")

    def classic(vsc):
        @vsc.randobj
        class Basic:
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(8)
                self.d = vsc.rand_bit_t(8)

            @vsc.constraint
            def ab_c(self):
                self.a < self.b
        return Basic

    def dc(vdc):
        @vdc.dataclass
        class Basic(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < self.b
        return Basic

    def cr(cr):
        class Basic(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('a', bits=8)
                self.add_rand_var('b', bits=8, order=1)
                self.add_rand_var('c', bits=8)
                self.add_rand_var('d', bits=8)
                self.add_constraint(lambda a, b: a < b, ('a', 'b'))
        return Basic

    def check(s):
        return s["a"] < s["b"] and all(0 <= s[k] < 256 for k in "abcd")


@workload
class Simple(Workload):
    name, family = "simple", "scalar"
    fields = ("a", "b")

    def classic(vsc):
        @vsc.randobj
        class Simple:
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                self.a < self.b
        return Simple

    def dc(vdc):
        @vdc.dataclass
        class Simple(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a < self.b
        return Simple

    def cr(cr):
        class Simple(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('a', bits=8)
                self.add_rand_var('b', bits=8, order=1)
                self.add_constraint(lambda a, b: a < b, ('a', 'b'))
        return Simple

    def check(s):
        return 0 <= s["a"] < s["b"] < 256


@workload
class Alu(Workload):
    """A multi-range `inside` on a 32-bit field."""
    name, family = "alu", "scalar"
    fields = ("op", "a", "b")

    def classic(vsc):
        @vsc.randobj
        class Alu:
            def __init__(self):
                self.op = vsc.rand_bit_t(4)
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint32_t()

            @vsc.constraint
            def c(self):
                self.op <= 7
                self.a < self.b
                self.a.inside(vsc.rangelist(1, 2, (100, 200)))
        return Alu

    def dc(vdc):
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
        return Alu

    def cr(cr):
        class Alu(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('op', bits=4, constraints=(lambda op: op <= 7,))
                self.add_rand_var('a', domain=[1, 2] + list(range(100, 201)))
                self.add_rand_var('b', bits=32)
                self.add_constraint(lambda a, b: a < b, ('a', 'b'))
        return Alu

    def check(s):
        return (s["op"] <= 7 and s["a"] < s["b"] < (1 << 32)
                and (s["a"] in (1, 2) or 100 <= s["a"] <= 200))


@workload
class Wide64(Workload):
    name, family = "wide64", "scalar"
    fields = ("x", "y")

    def classic(vsc):
        @vsc.randobj
        class Wide64:
            def __init__(self):
                self.x = vsc.rand_uint64_t()
                self.y = vsc.rand_uint64_t()

            @vsc.constraint
            def c(self):
                self.x < self.y
                self.x > 1000
        return Wide64

    def dc(vdc):
        @vdc.dataclass
        class Wide64(vdc.RandClass):
            x: vdc.u64 = vdc.rand()
            y: vdc.u64 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.x < self.y
                self.x > 1000
        return Wide64

    def cr(cr):
        class Wide64(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('x', bits=64, constraints=(lambda x: x > 1000,))
                self.add_rand_var('y', bits=64)
                self.add_constraint(lambda x, y: x < y, ('x', 'y'))
        return Wide64

    def check(s):
        return 1000 < s["x"] < s["y"] < (1 << 64)
