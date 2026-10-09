"""``randomize_with`` reuses the plan when a call site's inline block is unchanged
(V7, ``doc/notes/riscv_dv_vdc_port_plan.md`` §7).

An inline block used to disable the plan cache, so every ``randomize_with``
rebuilt and re-translated the whole problem. Now ``inline._reuse_block`` passes
the block from the previous call at the same site when the new block has the
same content, and the randomizer keys a plan on that block.

What must hold: an unchanged block keeps its plan, and any change -- to a
literal, to a referenced non-rand field, or to which call site is used --
still yields legal values.
"""
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.impl import ctor
from vsc.model.randomizer import _INLINE_PLANS_ATTR


class reg(IntEnum):
    ZERO = 0; RA = 1; SP = 2; GP = 3; TP = 4; T0 = 5; T1 = 6; T2 = 7


@vdc.dataclass
class Instr(vdc.RandClass):
    rs1: reg = vdc.rand()
    rd: reg = vdc.rand()
    imm: vdc.u8 = vdc.rand()
    limit: vdc.u8 = vdc.field(default=100)

    @vdc.constraint
    def c(self):
        self.imm < 200


def site_a(i, avail, reserved):
    with i.randomize_with() as it:
        it.rs1.inside(vdc.rangelist(*avail))
        it.rd.inside(vdc.rangelist(*avail))
        for r in reserved:
            it.rd != r


def site_b(i, avail):
    with i.randomize_with() as it:
        it.rd.inside(vdc.rangelist(*avail))
        it.imm < it.limit


def _inline_plans(cls):
    node = cls.__dict__.get(solve_view._SOLVE_MODEL_ATTR)
    return getattr(node.composite, _INLINE_PLANS_ATTR, None) if node else None


class TestInlineReuse(DcTestCase):

    def setUp(self):
        super().setUp()
        try:
            ctor.set_solver_backend("dv-solve")
        except Exception:
            self.skipTest("dv-solve back-end not available")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_unchanged_block_keeps_its_plan(self):
        avail, reserved = [reg.RA, reg.SP, reg.GP, reg.T0], [reg.SP]
        site_a(Instr(), avail, reserved)
        plans = _inline_plans(Instr)
        self.assertTrue(plans, "randomize_with was not plan-cached")
        before = dict(plans)
        for _ in range(20):
            i = Instr()
            site_a(i, avail, reserved)
            self.assertEqual(before, _inline_plans(Instr), "plan was rebuilt")
            self.assertIn(i.rs1, avail)
            self.assertIn(i.rd, avail)
            self.assertNotIn(i.rd, reserved)

    def test_changed_literals_at_one_site(self):
        sets = [([reg.RA, reg.SP, reg.GP], [reg.SP]),
                ([reg.T0, reg.T1, reg.T2], [reg.T0, reg.T2]),
                ([reg.TP], [])]
        for k in range(60):
            avail, reserved = sets[k % len(sets)]
            i = Instr()
            site_a(i, avail, reserved)
            self.assertIn(i.rs1, avail)
            self.assertIn(i.rd, avail)
            self.assertNotIn(i.rd, reserved)

    def test_two_sites_interleaved(self):
        a_avail = [reg.RA, reg.SP]
        b_avail = [reg.T1, reg.T2]
        for k in range(40):
            i = Instr()
            if k % 2:
                site_a(i, a_avail, [])
                self.assertIn(i.rd, a_avail)
            else:
                site_b(i, b_avail)
                self.assertIn(i.rd, b_avail)
                self.assertLess(i.imm, i.limit)

    def test_referenced_state_change_invalidates(self):
        for limit in (100, 5, 1, 50, 5):
            for _ in range(10):
                i = Instr(limit=limit)
                site_b(i, [reg.GP])
                self.assertLess(i.imm, limit)

    def test_plain_randomize_between_inline_calls(self):
        avail = [reg.RA, reg.SP]
        for k in range(30):
            i = Instr()
            if k % 3 == 0:
                i.randomize()
                self.assertLess(i.imm, 200)
            else:
                site_a(i, avail, [reg.SP])
                self.assertEqual(i.rd, reg.RA)
                self.assertIn(i.rs1, avail)
