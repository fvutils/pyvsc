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

from dc_test_case import DcTestCase, dvsolve_available
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.impl import ctor
from vsc.model.rand_state import RandState
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
        if not dvsolve_available():
            self.skipTest("dv-solve back-end not available")
        ctor.set_solver_backend("dv-solve")

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


def site_c(i, avail, k):
    # Each statement constrains one rand field, so all are T0.
    with i.randomize_with() as it:
        it.rd.inside(vdc.rangelist(*avail))
        it.imm < k


def site_d(i, k):
    # `rs1 != rd` ties two rand fields, which keeps that RandSet on the solver.
    with i.randomize_with() as it:
        it.rs1 != it.rd
        it.imm < k


class TestInlineRebind(DcTestCase):
    """A literal-only change at a call site moves the plan to the new block
    (`randomizer._plan_rebind`) instead of rebuilding it, when every inline
    statement is in a T0 RandSet. The values must be what a rebuild gives."""

    def setUp(self):
        super().setUp()
        if not dvsolve_available():
            self.skipTest("dv-solve back-end not available")
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _run(self, calls):
        """[(rs1, rd, imm)] for a fixed-seed sequence of site_c calls."""
        out = []
        i = Instr()
        i.set_randstate(RandState.mkFromSeed(7))
        for avail, k in calls:
            site_c(i, avail, k)
            out.append((i.rs1, i.rd, i.imm))
            self.assertIn(i.rd, avail)
            self.assertLess(i.imm, k)
        return out

    # Same rangelist length throughout: a different length is a structural
    # change, which is rebuilt.
    CALLS = [([reg.RA, reg.SP], 10), ([reg.T0, reg.T2], 3),
             ([reg.GP, reg.T1], 200), ([reg.RA, reg.TP], 1)] * 5

    def test_literal_change_moves_the_plan(self):
        import vsc.model.randomizer as rz
        calls = []
        orig = rz._rebind_blocks

        def spy(*a):
            r = orig(*a)
            calls.append(r)
            return r
        rz._rebind_blocks = spy
        try:
            self._run(self.CALLS)
        finally:
            rz._rebind_blocks = orig
        # The site's plans live on the class, so a block left by an earlier
        # test can count as one more.
        self.assertGreaterEqual(len(calls), len(self.CALLS) - 1)
        self.assertTrue(all(calls), "a literal-only change was rebuilt")

    def test_same_values_as_a_rebuild(self):
        import vsc.model.randomizer as rz
        with_rebind = self._run(self.CALLS)
        orig = rz._rebind_blocks
        rz._rebind_blocks = lambda *a: False
        try:
            without = self._run(self.CALLS)
        finally:
            rz._rebind_blocks = orig
        self.assertEqual(with_rebind, without)

    def test_solver_randset_is_rebuilt(self):
        import vsc.model.randomizer as rz
        calls = []
        orig = rz._rebind_blocks

        def spy(*a):
            r = orig(*a)
            calls.append(r)
            return r
        rz._rebind_blocks = spy
        try:
            for k in (5, 9, 2, 30, 1):
                i = Instr()
                site_d(i, k)
                self.assertNotEqual(i.rs1, i.rd)
                self.assertLess(i.imm, k)
        finally:
            rz._rebind_blocks = orig
        self.assertTrue(calls)
        self.assertFalse(any(calls), "statement in a solver RandSet was rebound")

    def test_empty_domain_after_change_reports_failure(self):
        site_c(Instr(), [reg.RA], 10)
        with self.assertRaises(vdc.SolveFailure):
            site_c(Instr(), [reg.RA], 0)     # imm < 0 has no unsigned value
        i = Instr()
        site_c(i, [reg.SP], 4)               # and the site still works after
        self.assertEqual(i.rd, reg.SP)
        self.assertLess(i.imm, 4)
