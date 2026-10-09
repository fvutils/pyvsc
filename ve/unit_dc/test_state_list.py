"""Non-rand ``list`` fields as constraint inputs (the riscv-dv ``randomize_gpr``
shape: ``rd inside avail_regs``, ``rd != reserved[i]``).

Defects found while porting riscv-dv pygen to vdc
(``doc/notes/riscv_dv_vdc_port_plan.md`` §7):

- **V4.** A non-rand list's length was fixed from the class default
  (``vdc.field`` called the ``default_factory`` once), not taken from the
  instance. An empty default dropped the constraint; a shorter default dropped
  table entries; a longer one padded the table with zeros. No error was raised.
- **V6.** ``x.inside(rangelist(self.tbl))`` could not be snapshotted for the
  plan cache, so the problem was rebuilt on every call (385 -> 38 us in the
  ``gpr_variants`` benchmark).
"""
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.dc import solve_view
from vsc.impl import ctor
from vsc.model.randomizer import _PLAN_ATTR


class reg(IntEnum):
    ZERO = 0; RA = 1; SP = 2; GP = 3; TP = 4; T0 = 5; T1 = 6; T2 = 7


@vdc.dataclass
class Tbl(vdc.RandClass):
    x: vdc.u8 = vdc.rand()
    tbl: list[vdc.u8] = vdc.field(default_factory=list)

    @vdc.constraint
    def c(self):
        self.x.inside(vdc.rangelist(self.tbl))


@vdc.dataclass
class EnumTbl(vdc.RandClass):
    r: reg = vdc.rand()
    avail: list[reg] = vdc.field(default_factory=lambda: [reg.ZERO, reg.RA])
    reserved: list[reg] = vdc.field(default_factory=list)

    @vdc.constraint
    def c(self):
        self.r.inside(vdc.rangelist(self.avail))
        with vdc.foreach(self.reserved, idx=True) as k:
            self.r != self.reserved[k]


def _plan(cls):
    node = cls.__dict__.get(solve_view._SOLVE_MODEL_ATTR)
    return getattr(node.composite, _PLAN_ATTR, None) if node else None


class TestStateList(DcTestCase):

    # ---- V4: the instance's length is used --------------------------------- #
    def test_length_follows_instance(self):
        for tbl in ([1, 2], [5, 6, 7], [9], [3, 4, 5, 6, 7, 8]):
            seen = set()
            for _ in range(40):
                o = Tbl(tbl=list(tbl))
                o.randomize()
                seen.add(int(o.x))
            self.assertLessEqual(seen, set(tbl), "table %r" % (tbl,))
            if len(tbl) > 1:
                self.assertGreater(len(seen), 1)

    def test_length_changes_on_one_instance(self):
        o = Tbl(tbl=[1, 2, 3])
        for tbl in ([1, 2, 3], [7], [10, 20, 30, 40, 50], [7]):
            o.tbl = list(tbl)
            for _ in range(15):
                o.randomize()
                self.assertIn(int(o.x), tbl)

    def test_enum_tables(self):
        cases = [([reg.SP, reg.GP, reg.TP], [reg.GP]),
                 ([reg.T0, reg.T1, reg.T2, reg.RA], []),
                 ([reg.T0, reg.T1], [reg.T0])]
        for avail, reserved in cases:
            for _ in range(30):
                o = EnumTbl(avail=list(avail), reserved=list(reserved))
                o.randomize()
                self.assertIn(o.r, avail)
                self.assertNotIn(o.r, reserved)

    # ---- V6: the plan is kept, and still invalidated by a change ----------- #
    def test_table_keeps_its_plan(self):
        # The plan cache is dv-solve only; pin it rather than skip.
        try:
            ctor.set_solver_backend("dv-solve")
        except Exception:
            self.skipTest("dv-solve back-end not available")
        try:
            o = Tbl(tbl=[4, 5, 6])
            o.randomize()
            plan = _plan(Tbl)
            self.assertIsNotNone(plan, "rangelist over a list was not cached")
            for _ in range(15):
                o = Tbl(tbl=[4, 5, 6])
                o.randomize()
                self.assertIs(plan, _plan(Tbl), "plan was rebuilt")
                self.assertIn(int(o.x), (4, 5, 6))
        finally:
            ctor.set_solver_backend(None)

    def test_same_length_value_change_invalidates(self):
        a, b = [1, 2, 3], [11, 12, 13]
        for k in range(60):
            tbl = a if k % 2 else b
            o = Tbl(tbl=list(tbl))
            o.randomize()
            self.assertIn(int(o.x), tbl)
