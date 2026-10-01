"""
Micro-benchmark for ``randc`` cyclic randomization in the dataclass front-end.

Compares per-draw cost of a plain ``rand`` field against ``randc`` fields of a few
domain sizes, and measures within-cycle cost growth (the tell-tale of the O(D^2)
value-exclusion approach vs the O(1)/draw separable fast path in vsc/dc/cyclic.py).

    PYTHONPATH=src VSC_SOLVER=dv-solve python -W ignore benchmarks/bench_randc.py [N]
"""
import sys
import time
from enum import IntEnum

sys.path.insert(0, "src")
import vsc.dc as vdc


class _Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    WHITE = 3
    BLACK = 4


def _per_draw_us(fn, n):
    t = time.perf_counter()
    fn()
    return (time.perf_counter() - t) / n * 1e6


@vdc.dataclass
class _Plain(vdc.RandClass):
    x: vdc.u8 = vdc.rand()


@vdc.dataclass
class _RandC4(vdc.RandClass):
    x: vdc.u4 = vdc.randc()      # domain 16


@vdc.dataclass
class _RandC8(vdc.RandClass):
    x: vdc.u8 = vdc.randc()      # domain 256


@vdc.dataclass
class _RandCEnum(vdc.RandClass):
    c: _Color = vdc.randc()      # enum domain 5

    @vdc.constraint
    def k(self):
        self.c != _Color.BLACK   # feasible domain 4


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

    plain = _Plain()
    us_plain = _per_draw_us(lambda: [plain.randomize() for _ in range(n)], n)

    c4 = _RandC4()
    us_c4 = _per_draw_us(lambda: [c4.randomize() for _ in range(n)], n)

    c8 = _RandC8()
    us_c8 = _per_draw_us(lambda: [c8.randomize() for _ in range(n)], n)

    ce = _RandCEnum()
    us_ce = _per_draw_us(lambda: [ce.randomize() for _ in range(n)], n)

    # Within one 256-value cycle: exclusion grows O(D); the fast path stays flat.
    c8b = _RandC8()
    times = []
    for _ in range(256):
        t = time.perf_counter()
        c8b.randomize()
        times.append((time.perf_counter() - t) * 1e6)
    early = sum(times[:16]) / 16
    late = sum(times[-16:]) / 16

    print("plain rand u8        : %7.1f us/draw" % us_plain)
    print("randc u4 (D=16)      : %7.1f us/draw   (%.1fx plain)" % (us_c4, us_c4 / us_plain))
    print("randc u8 (D=256)     : %7.1f us/draw   (%.1fx plain)" % (us_c8, us_c8 / us_plain))
    print("randc enum (D=4/5)   : %7.1f us/draw   (%.1fx plain)" % (us_ce, us_ce / us_plain))
    print("randc u8 within-cycle: first16=%6.1f  last16=%6.1f us  (%.1fx growth)" % (
        early, late, late / early))


if __name__ == "__main__":
    main()
