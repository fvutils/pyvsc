"""Class-level constants in constraints (V1, ``vsc/dc/class_const.py``).

riscv-dv's instruction classes fix their opcode identity per subclass
(``instr_name``, ``format``, ``has_rd``, ...) while the shared base class's
constraints guard on it: ``if self.instr_name in (SLLI, SRLI): imm[11:5] == 0``.
Read as class attributes, these are constants of the subclass. The type model
replaces them with literals and folds the guards they decide, so each subclass
solves only what applies to it. Before this, such a read failed at the first
randomize with "constraint references unknown field".
"""
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.dc import constraint_ir as ir


class Op(IntEnum):
    ADD = 0
    SLLI = 1
    SRLI = 2


@vdc.dataclass
class Instr(vdc.RandClass):
    imm: vdc.u32 = vdc.rand()
    rd: vdc.u8 = vdc.rand()

    @vdc.constraint
    def imm_c(self):
        with vdc.if_then(self.name.inside(vdc.rangelist(Op.SLLI, Op.SRLI))):
            self.imm[11:5] == 0
        with vdc.if_then(self.xlen == 32):
            self.imm[31:12] == 0
        with vdc.else_then:
            self.imm[31:12] == 0xFFFFF

    @vdc.constraint
    def rd_c(self):
        with vdc.implies(self.has_rd):
            self.rd < 8
        with vdc.if_then(~self.has_rd):
            self.rd == 0


class Slli(Instr):
    name = Op.SLLI
    xlen = 32
    has_rd = True


class Add64(Instr):
    name = Op.ADD
    xlen = 64
    has_rd = False


def _stmt_types(cls):
    tm = cls()._get_type_model()
    return {p.name: [type(s) for s in p.stmts] for p in tm.constraints}


class TestClassConst(DcTestCase):

    def test_guards_fold_per_subclass(self):
        # Every guard reads only class constants, so nothing conditional is left.
        self.assertEqual(_stmt_types(Slli), {
            "imm_c": [ir.IRConstraintExpr, ir.IRConstraintExpr],
            "rd_c": [ir.IRConstraintExpr]})
        self.assertEqual(_stmt_types(Add64), {
            "imm_c": [ir.IRConstraintExpr],
            "rd_c": [ir.IRConstraintExpr]})

    def test_taken_branches_hold(self):
        s = Slli()
        for _ in range(50):
            s.randomize()
            self.assertEqual((s.imm >> 5) & 0x7F, 0)
            self.assertEqual(s.imm >> 12, 0)
            self.assertLess(s.rd, 8)

    def test_else_branch_and_dropped_guards(self):
        a = Add64()
        seen_mid = False
        for _ in range(50):
            a.randomize()
            self.assertEqual(a.imm >> 12, 0xFFFFF)
            self.assertEqual(a.rd, 0)
            seen_mid |= ((a.imm >> 5) & 0x7F) != 0
        # The SLLI/SRLI guard is false for ADD: imm[11:5] is unconstrained.
        self.assertTrue(seen_mid)

    def test_subclasses_do_not_share_programs(self):
        # Building Add64 must not change what Slli solves, and vice versa.
        Add64().randomize()
        s = Slli()
        s.randomize()
        self.assertEqual(s.imm >> 12, 0)

    def test_field_is_never_folded(self):
        # A non-rand field also has a class attribute (its default). It is
        # instance state, so it must stay a solver input, not a constant.
        @vdc.dataclass
        class Moded(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            mode: vdc.u8 = vdc.field(default=1)

            @vdc.constraint
            def c(self):
                with vdc.if_then(self.mode == 1):
                    self.x == 5
                with vdc.else_then:
                    self.x == 9

        m = Moded()
        m.randomize()
        self.assertEqual(m.x, 5)
        m.mode = 0
        m.randomize()
        self.assertEqual(m.x, 9)

    def test_foreach_variable_shadows_class_attr(self):
        @vdc.dataclass
        class Arr(vdc.RandClass):
            a: list[vdc.u8] = vdc.rand(size=4)

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.a, idx=True) as i:
                    self.a[i] == i

        class Sub(Arr):
            i = 7       # same name as the loop index: must not be substituted

        s = Sub()
        s.randomize()
        self.assertEqual(list(s.a), [0, 1, 2, 3])

    def test_non_constant_attribute_is_left_alone(self):
        # A method is not a constant: the read stays a field reference and
        # fails at lowering, as it did before.
        @vdc.dataclass
        class M(vdc.RandClass):
            x: vdc.u8 = vdc.rand()

            def helper(self):
                return 1

            @vdc.constraint
            def c(self):
                self.x == self.helper

        with self.assertRaises(KeyError):
            M().randomize()
