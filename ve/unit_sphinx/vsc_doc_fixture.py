"""Fixture classes for the vsc.sphinx tests."""
from enum import IntEnum

import vsc
import vsc.dc as vdc


class Op(IntEnum):
    """ALU operations."""
    ADD = 0
    SUB = 1
    AND = 2
    OR = 3


@vdc.dataclass
class AluTxn(vdc.RandClass):
    """An ALU transaction."""

    op: Op = vdc.rand()                 #: Operation select.
    a: vdc.u32 = vdc.rand(domain=(1, 1000))
    """First operand."""
    b: vdc.u32 = vdc.rand()
    tags: list[vdc.u8] = vdc.rand(max_size=4)
    mode: vdc.u2 = vdc.field(default=1)

    @vdc.constraint
    def c_op(self):
        """Operands ascending; both small."""
        self.a < self.b
        self.c_small(64)

    @vdc.constraint.generic
    def c_small(self, n=16):
        """Both operands below *n*."""
        self.a < n
        self.b < n

    def pre_randomize(self):
        """Hook that stays a method."""

    def helper(self):
        """An ordinary method."""


@vdc.dataclass
class WideTxn(AluTxn):
    """Adds a field and overrides ``c_op``."""

    w: vdc.s16 = vdc.rand()

    @vdc.constraint
    def c_op(self):
        self.a < self.b
        self.w > 0


@vdc.dataclass
class AluCov(vdc.Covergroup):
    """ALU coverage."""

    op: vdc.Coverpoint[Op] = vdc.coverpoint()       #: Operation.
    mode: vdc.Coverpoint[vdc.u2] = vdc.coverpoint(
        bins=dict(
            lo=vdc.bin(0, 1),           # idle modes
            hi=vdc.bin(2, 3, doc="Active modes."),
        ))
    #: Pull coverpoint over a sample input.
    val: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        lambda s: s.x + 1, iff=lambda s: s.x != 0,
        bins=dict(v=vdc.bin_array([4], (0, 255))),
        options=dict(weight=2))
    x: vdc.u8 = vdc.sample_arg()        #: Raw input value.
    op_x_mode: vdc.Cross = vdc.cross(
        lambda s: s.op, lambda s: s.mode,
        ignore_bins=dict(
            # ADD never runs in the idle modes
            add_idle=lambda s: vdc.binsof(s.op).intersect([0])
                               & vdc.binsof(s.mode).intersect([(0, 1)])))


@vsc.randobj
class Classic(object):
    """A classic randobj."""

    def __init__(self, width=8):
        self.a = vsc.rand_bit_t(8)

    @vsc.constraint
    def ab_c(self):
        """Classic constraint."""
        self.a < 10

    @vsc.dynamic_constraint
    def small(self):
        self.a < 4
