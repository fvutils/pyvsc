'''
Typed sample() (design §1 / impl plan TS): ``@vdc.dataclass`` synthesizes a
per-type ``sample`` whose signature lists the real push-coverpoint / sample_arg
formals, so ``inspect.signature`` works and Python raises native arg errors. The
binding behavior is unchanged from the generic binder (parity asserted below).
'''
import inspect
from enum import IntEnum, auto

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestTypedSample(DcTestCase):

    def test_signature_lists_formals_in_order(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        sig = inspect.signature(cg.sample)
        self.assertEqual(list(sig.parameters), ["a", "b"])
        # int annotation on non-enum push coverpoints
        self.assertEqual(sig.parameters["a"].annotation, int)
        self.assertEqual(sig.parameters["b"].annotation, int)

    def test_signature_enum_annotation_and_arg_order(self):
        class Op(IntEnum):
            RD = 0
            WR = auto()

        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            op: vdc.Coverpoint[Op] = vdc.coverpoint()
            addr: vdc.u8 = vdc.sample_arg()
            addr_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.addr, bins=dict(a=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        sig = inspect.signature(cg.sample)
        # push coverpoints (declaration order) then sample_arg fields; the pull
        # coverpoint addr_cp is not a formal.
        self.assertEqual(list(sig.parameters), ["op", "addr"])
        self.assertIs(sig.parameters["op"].annotation, Op)
        self.assertEqual(sig.parameters["addr"].annotation, int)

    def test_positional_and_keyword_bind(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0, 4)               # positional: a->0, b->4
        cg.sample(b=8, a=4)           # keyword (any order)
        self.assertEqual(cg.a.get_coverage(), 50)   # bins 0,1
        self.assertEqual(cg.b.get_coverage(), 50)   # bins 1,2

    def test_unset_keeps_previous(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))
            b: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(b=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        cg.sample(0, 0)
        cg.sample(a=4)                # b unset -> keeps prior value (0)
        self.assertEqual(cg.a.get_coverage(), 50)
        self.assertEqual(cg.b.get_coverage(), 25)

    def test_too_many_positional_raises(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        with self.assertRaises(TypeError) as ctx:
            cg.sample(1, 2)
        self.assertIn("positional", str(ctx.exception))

    def test_unknown_keyword_raises(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))

        cg = my_cg()
        with self.assertRaises(TypeError) as ctx:
            cg.sample(nope=1)
        self.assertIn("nope", str(ctx.exception))

    def test_user_override_respected(self):
        # A class-defined sample() is not replaced; super().sample() still works.
        class Pkt:
            def __init__(self, addr):
                self.addr = addr

        @vdc.dataclass
        class PktCov(vdc.Covergroup):
            addr: vdc.u8 = vdc.sample_arg()
            addr_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                lambda s: s.addr, bins=dict(a=vdc.bin_array([4], (0, 16))))

            def sample(self, pkt):
                self.assign_from(pkt)
                super().sample()

        cov = PktCov()
        # The installer skipped: signature is the user's (pkt), not synthesized.
        self.assertEqual(list(inspect.signature(cov.sample).parameters), ["pkt"])
        cov.sample(Pkt(0))
        cov.sample(Pkt(4))
        self.assertEqual(cov.addr_cp.get_coverage(), 50)

    def test_docstring_lists_formals(self):
        @vdc.dataclass
        class my_cg(vdc.Covergroup):
            a: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
                bins=dict(a=vdc.bin_array([4], (0, 16))))

        self.assertIn("a", my_cg.sample.__doc__)
