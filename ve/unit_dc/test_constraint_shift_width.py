'''
Dataclass-front-end adaptation of t_constraint_shift_width.v and the bit-fairness
gate from t_randomize_shift_distribution.v.

Mixed-width shift alignment: a wide (37-bit) ``address`` aligned to ``1 << size``
where ``size`` is a narrow (4-bit) rand shift amount — the shift RHS must be
zero-extended to the LHS width for ``address % (1 << size) == 0`` to hold.  Three
packets mirror the SV cases: variable shift (pinned + free), constant shift, and a
mixed-width shift inside an implication consequent.

The distribution case pins ``value < (1 << m_size)`` (a power-of-two upper bound
via a constant shift, ``m_size`` non-rand) and asserts every FREE bit is a fair
coin flip over 200 trials — the pre-fix boundary-bias bug pinned free bits near
K-1 (70-90% ones).  Band [70, 130] (35-65%) is ~4 sigma off the fair-50% mean, so
a uniform mechanism passes ~99.7%/run while a boundary bias overruns it.  Bits at
or above ``m_size`` must stay 0.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class AlignedPacket(vdc.RandClass):
    address: vdc.bitv = vdc.rand(width=37)
    size: vdc.u4 = vdc.rand()

    @vdc.constraint
    def c_aligned(self):
        self.address % (1 << self.size) == 0


@vdc.dataclass
class ConstShiftPacket(vdc.RandClass):
    address: vdc.bitv = vdc.rand(width=37)

    @vdc.constraint
    def c_aligned(self):
        self.address % (1 << 10) == 0        # aligned to 1024


@vdc.dataclass
class ImplicationShift(vdc.RandClass):
    # txn_type: 0=READ, 1=WRITE, 2=IDLE (READ/WRITE => alignment required)
    txn_type: vdc.u2 = vdc.rand()
    size: vdc.u4 = vdc.rand()
    address: vdc.bitv = vdc.rand(width=37)

    @vdc.constraint
    def c_addr(self):
        with vdc.implies((self.txn_type == 0) | (self.txn_type == 1)):
            self.address % (1 << self.size) == 0


@vdc.dataclass
class RegField(vdc.RandClass):
    value: vdc.u64 = vdc.rand()
    m_size: vdc.u32 = 0                       # non-rand; set per instance

    @vdc.constraint
    def c_field_valid(self):
        self.value < (1 << self.m_size)


class TestShiftWidth(DcTestCase):

    def test_variable_shift_pinned(self):
        # size==6 => address aligned to 1<<6 == 64.
        pkt = AlignedPacket()
        for _ in range(10):
            with pkt.randomize_with() as it:
                it.size == 6
            self.assertEqual(int(pkt.address) % 64, 0)

    def test_variable_shift_free(self):
        # Unconstrained size: address must be aligned to 1<<size each draw.
        pkt = AlignedPacket()
        seen = set()
        for _ in range(40):
            pkt.randomize()
            s = int(pkt.size)
            self.assertEqual(int(pkt.address) % (1 << s), 0,
                             "addr=0x%x not aligned to 1<<%d" % (pkt.address, s))
            seen.add(s)
        self.assertGreater(len(seen), 1, "size never varied")

    def test_constant_shift_wide(self):
        pkt = ConstShiftPacket()
        for _ in range(20):
            pkt.randomize()
            self.assertEqual(int(pkt.address) % 1024, 0)

    def test_implication_shift(self):
        # txn READ(0)/WRITE(1) => aligned to 1<<size; IDLE(2) => free.
        pkt = ImplicationShift()
        for _ in range(15):
            with pkt.randomize_with() as it:
                it.txn_type == 0
                it.size == 4
            self.assertEqual(int(pkt.address) % 16, 0)
        # IDLE leaves address unconstrained (no alignment forced).
        saw_unaligned = False
        for _ in range(40):
            with pkt.randomize_with() as it:
                it.txn_type == 2
                it.size == 4
            if int(pkt.address) % 16 != 0:
                saw_unaligned = True
                break
        self.assertTrue(saw_unaligned,
                        "IDLE should not force alignment (implication vacuous)")

    def _bit_fairness(self, size, trials=200, lo=70, hi=130):
        f = RegField()
        # m_size is non-rand state: set it directly on the instance.
        object.__setattr__(f, "m_size", size)
        ones = [0] * size
        for _ in range(trials):
            f.randomize()
            v = int(f.value)
            self.assertLess(v, 1 << size, "value >= 1<<%d: 0x%x" % (size, v))
            for b in range(size):
                if (v >> b) & 1:
                    ones[b] += 1
        for b in range(size):
            self.assertLessEqual(
                ones[b], hi,
                "bit %d biased high (%d/%d ones) — boundary bias" % (b, ones[b], trials))
            self.assertGreaterEqual(
                ones[b], lo,
                "bit %d biased low (%d/%d ones)" % (b, ones[b], trials))

    def test_bit_fairness_15(self):
        self._bit_fairness(15)

    def test_bit_fairness_32(self):
        self._bit_fairness(32)
