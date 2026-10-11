"""
Example 4 — functional coverage: covergroup, coverpoints, bins, cross.

Run:  PYTHONPATH=src python examples/dc/04_coverage.py
"""
from enum import IntEnum, auto

import vsc.dc as vdc


class Op(IntEnum):
    ADD = 0
    SUB = auto()
    AND = auto()
    OR = auto()


@vdc.dataclass
class AluCov(vdc.Covergroup):
    # Push coverpoints: the synthesized sample() takes (op, mode) in order.
    op: vdc.Coverpoint[Op] = vdc.coverpoint()                  # enum auto-bins
    mode: vdc.Coverpoint[vdc.u2] = vdc.coverpoint(
        bins=dict(lo=vdc.bin(0, 1), hi=vdc.bin(2, 3)))
    op_x_mode: vdc.Cross = vdc.cross(lambda s: s.op, lambda s: s.mode)


def main():
    cov = AluCov()
    # Sample the full cross product (4 ops x 2 mode-bins).
    for op in Op:
        for mode in (0, 2):
            cov.sample(op, mode)

    print(f"op coverage   = {cov.op.get_coverage()}%")
    print(f"mode coverage = {cov.mode.get_coverage()}%")
    print(f"cross coverage= {cov.op_x_mode.get_coverage()}%")
    print(f"covergroup    = {cov.get_coverage()}%")
    assert cov.op.get_coverage() == 100
    assert cov.mode.get_coverage() == 100
    assert cov.op_x_mode.get_coverage() == 100


if __name__ == "__main__":
    main()
