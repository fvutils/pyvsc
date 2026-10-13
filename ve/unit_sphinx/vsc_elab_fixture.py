"""Classes documented by the elaboration tests (``vsc_covergroup_elaborate``,
``vsc_classic_instantiate``). The "Elaborated:" comments give the counts
elaboration must report; they are plain comments, not ``#:``, so they do not
reach the documentation the tests search."""
from enum import IntEnum

import vsc
import vsc.dc as vdc


class Kind(IntEnum):
    A = 0
    B = 1
    C = 2


@vdc.dataclass
class ElabCov(vdc.Covergroup):
    """Coverage whose bin counts need the runtime model."""

    # Elaborated: 64 bins of 4 values over 0..255.
    #: Automatic bins over a width.
    auto8: vdc.Coverpoint[vdc.u8] = vdc.coverpoint()
    # Elaborated: 16 bins of 1 value over -8..7.
    #: Automatic bins over a signed width.
    auto_s4: vdc.Coverpoint[vdc.s4] = vdc.coverpoint()
    # Elaborated: 3 bins of 85 to 87 values over 0..255.
    #: Automatic bins of uneven size.
    uneven: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(options=dict(auto_bin_max=3))
    # Elaborated: 2 bins (A, B).
    #: Enum with one member ignored.
    kind: vdc.Coverpoint[Kind] = vdc.coverpoint(
        ignore_bins=dict(no_c=vdc.bin(2)))
    # Elaborated: each -> 7 bins, gone -> 0; 7 in all.
    #: Explicit bins trimmed by ignore bins.
    val: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(
            each=vdc.bin_array([], (0, 7)),     # one bin per value
            gone=vdc.bin((100, 110)),           # wholly ignored
        ),
        ignore_bins=dict(skip=vdc.bin(3, (100, 110))))
    # Elaborated: 2 x 7 = 14 bins: 7 ignored (A row), 4 illegal (B with
    # 4..7), 3 counted.
    #: Cross with ignored and illegal selections.
    kind_x_val: vdc.Cross = vdc.cross(
        lambda s: s.kind, lambda s: s.val,
        ignore_bins=dict(
            a_row=lambda s: vdc.binsof(s.kind).intersect([0])),
        illegal_bins=dict(
            b_hi=lambda s: vdc.binsof(s.kind).intersect([1])
            & vdc.binsof(s.val).intersect([(4, 7)])))

    post_init_calls = 0

    def __post_init__(self):
        type(self).post_init_calls += 1
        super().__post_init__()


@vdc.dataclass
class DefaultsCov(vdc.Covergroup):
    """A selection reading a sample_arg's default."""

    limit: int = vdc.sample_arg(default=63)
    a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(q=vdc.bin_array([4], (0, 255))))
    b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(q=vdc.bin_array([4], (0, 255))))
    # Elaborated: 16 bins; a's first quarter ignored: 4 ignored, 12 counted.
    #: Cross whose selection reads ``limit``.
    a_x_b: vdc.Cross = vdc.cross(
        lambda s: s.a, lambda s: s.b,
        ignore_bins=dict(low=lambda s: vdc.binsof(s.a).intersect([(0, s.limit)])))


@vdc.dataclass
class BrokenCov(vdc.Covergroup):
    """A selection needing a configuration object; cannot be elaborated."""

    cfg: object = vdc.cg_arg()
    a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(q=vdc.bin_array([4], (0, 255))))
    b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(q=vdc.bin_array([4], (0, 255))))
    a_x_b: vdc.Cross = vdc.cross(
        lambda s: s.a, lambda s: s.b,
        ignore_bins=dict(
            low=lambda s: vdc.binsof(s.a).intersect([(0, s.cfg.limit)])))


class Mode(IntEnum):
    RD = 0
    WR = 1


@vsc.randobj
class ClassicPkt(object):
    """A classic packet."""

    def __init__(self):
        self.addr = vsc.rand_bit_t(12)          #: Target address.
        #: Payload bytes.
        self.data = vsc.rand_list_t(vsc.uint8_t(), 4)
        self.extra = vsc.randsz_list_t(vsc.uint8_t())
        self.mode = vsc.rand_enum_t(Mode)
        self.count = vsc.uint16_t(5)
        self.offset = vsc.int8_t()
        self.helper = 3                         # plain Python: not a field

    @vsc.constraint
    def c_addr(self):
        """Low addresses only."""
        self.addr < 0x100


@vsc.randobj
class ClassicHdr(object):
    """A header."""

    def __init__(self):
        self.kind = vsc.rand_bit_t(2)


@vsc.randobj
class ClassicSub(ClassicPkt):
    """Adds fields."""

    def __init__(self):
        super().__init__()
        self.tag = vsc.rand_bit_t(3)            #: Sub-class tag.
        self.hdr = vsc.rand_attr(ClassicHdr())
        self.hdrs = vsc.rand_list_t(ClassicHdr(), 2)
        self.meta = vsc.attr(ClassicHdr())


@vsc.randobj
class NeedsInit(object):
    """Needs a constructor argument; cannot be instantiated."""

    def __init__(self, width):
        self.a = vsc.rand_bit_t(width)


@vsc.covergroup
class ClassicCov(object):
    """Classic coverage."""

    def __init__(self):
        self.with_sample(dict(addr=vsc.bit_t(12), mode=vsc.enum_t(Mode)))
        #: Address ranges.
        self.cp_addr = vsc.coverpoint(self.addr, bins=dict(
            low=vsc.bin((0, 0xff)),             # first page
            rest=vsc.bin_array([3], (0x100, 0xfff))))
        self.cp_mode = vsc.coverpoint(self.mode)
        self.cp_auto = vsc.coverpoint(self.addr)
        self.cr = vsc.cross([self.cp_addr, self.cp_mode], ignore_bins=dict(
            low_wr=lambda a, m: a.intersect([(0, 0xff)]) and m.intersect([1])))
