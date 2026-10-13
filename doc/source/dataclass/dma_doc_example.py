"""A DMA descriptor and its coverage, documented with ``vsc.sphinx``.

This module is the example on the "Documenting classes with Sphinx" page;
the page is built from it with plain ``automodule``.
"""
from enum import IntEnum

import vsc.dc as vdc


class Burst(IntEnum):
    """Burst type of a transfer."""
    FIXED = 0
    INCR = 1
    WRAP = 2


@vdc.dataclass
class DmaDesc(vdc.RandClass):
    """One DMA transfer descriptor."""

    burst: Burst = vdc.rand()                   #: Burst type.
    src: vdc.u32 = vdc.rand()                   #: Source byte address.
    dst: vdc.u32 = vdc.rand()                   #: Destination byte address.
    length: vdc.u16 = vdc.rand(domain=(1, 4096))
    """Transfer length in bytes."""
    strobes: list[vdc.u4] = vdc.rand(max_size=16)   #: Byte enables, one per beat.

    @vdc.constraint
    def c_align(self):
        """Addresses are word aligned."""
        self.src % 4 == 0
        self.dst % 4 == 0

    @vdc.constraint
    def c_page(self):
        """A transfer stays inside one 4 KiB page, and source and destination
        do not overlap."""
        self.src % 4096 + self.length <= 4096
        self.c_disjoint()

    @vdc.constraint.generic
    def c_disjoint(self):
        """The source and destination ranges are disjoint."""
        self.src + self.length <= self.dst or self.dst + self.length <= self.src


@vdc.dataclass
class DmaCov(vdc.Covergroup):
    """Coverage of the descriptors a test generated."""

    burst: vdc.Coverpoint[Burst] = vdc.coverpoint()    #: Burst type.
    #: Transfer length.
    length: vdc.Coverpoint[vdc.u16] = vdc.coverpoint(
        bins=dict(
            single=vdc.bin_array([1], (1, 4)),         # one beat
            short=vdc.bin_array([4], (5, 256)),        # up to 64 beats
            long=vdc.bin_array([1], (257, 4096), doc="Longer, up to a page."),
        ))
    burst_x_length: vdc.Cross = vdc.cross(
        lambda s: s.burst, lambda s: s.length,
        ignore_bins=dict(
            # A fixed burst is never longer than one beat
            fixed_long=lambda s: vdc.binsof(s.burst).intersect([0])
                                 & vdc.binsof(s.length).intersect([(5, 4096)])))
