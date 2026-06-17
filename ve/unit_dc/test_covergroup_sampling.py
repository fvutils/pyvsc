'''
Dataclass-front-end coverage sampling ergonomics (design §5.4): the synthesized
sample() binds push coverpoints / sample_arg formals positionally (declaration
order) then by name; unset formals keep their previous value; an overridden
sample() can use assign_from() then super().sample().
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestCovergroupSampling(DcTestCase):

    def test_keyword_and_partial(self):

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0, 0)                  # a->bin0, b->bin0
        cg.sample(a=4)                   # only a; b keeps prior value (0)
        self.assertEqual(cg.a.get_coverage(), 50)   # bins 0,1
        self.assertEqual(cg.b.get_coverage(), 25)   # bin 0 only (kept)
        cg.sample(b=4)                   # only b; a keeps prior value (4)
        self.assertEqual(cg.b.get_coverage(), 50)

    def test_resample_persists(self):
        # A bare re-sample re-bins the current staged values.

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.a.set(8)                      # stage via .set()
        cg.sample()                      # bin 2
        self.assertEqual(cg.a.get_coverage(), 25)
        cg.sample()                      # same value -> no new bin
        self.assertEqual(cg.a.get_coverage(), 25)

    def test_override_sample_assign_from(self):
        # Override sample() to extract from a producer object, then run the core
        # pass via super().sample().

        class Pkt:
            def __init__(self, addr, kind):
                self.addr = addr
                self.kind = kind

        @vdc.dataclass
        class PktCov(vdc.Covergroup):
            addr: vdc.u8 = vdc.sample_arg()
            kind: vdc.u2 = vdc.sample_arg()
            addr_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.addr, bins=dict(a=vdc.bin_array([4], (0, 16))))
            kind_cp: vdc.Coverpoint[vdc.u2] = vdc.coverpoint(lambda s: s.kind)

            def sample(self, pkt):
                self.assign_from(pkt)
                super().sample()

        cov = PktCov()
        cov.sample(Pkt(0, 0))
        cov.sample(Pkt(4, 3))
        self.assertEqual(cov.addr_cp.get_coverage(), 50)   # bins 0,1
        self.assertEqual(cov.kind_cp.get_coverage(), 50)   # kinds 0,3 of 0..3
