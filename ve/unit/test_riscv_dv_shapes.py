"""Constraint shapes from riscv-dv's Python generator (pygen).

pygen randomizes one instruction object per generated instruction with an
inline constraint that reads its *stream* object, which is never randomized
itself:

    with instr.randomize_with():
        with vsc.if_then(self.avail_regs.size > 0):
            with vsc.if_then(instr.has_rd):
                instr.rd.inside(vsc.rangelist(self.avail_regs))

and builds each instruction by deep-copying a template. Each test is one
defect that shape exposed (benchmarks/perf/riscv_dv.py runs pygen itself):

  * a declared-rand field of an object never randomized was treated as a
    random variable when another object's constraint read it, so the
    stream's `avail_regs.size` was overwritten with a random value;
  * `x.inside(vsc.rangelist(<randsz list>))` was dropped by the Boolector
    path, so `x` ignored the list;
  * deep-copying an object that dv-solve had randomized failed on the cached
    native plan;
  * an `inside` guard over non-random fields wasn't folded to a constant
    (ExprInModel had no val()), which sent the whole RandSet to BV-SAT.
"""
import copy
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend

from vsc_test_case import VscTestCase, requires_boolector


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


def _boolector_available():
    # select_backend raises for a back-end that is not installed.
    try:
        return select_backend("boolector").available()
    except Exception:
        return False


def _backends():
    out = []
    if _boolector_available():
        out.append("boolector")
    if _dvsolve_available():
        out.append("dv-solve")
    return out


@vsc.randobj
class Instr:
    def __init__(self):
        self.rd = vsc.rand_bit_t(5)
        self.rs1 = vsc.rand_bit_t(5)
        self.has_rd = vsc.bit_t(1, i=1)
        self.kind = vsc.bit_t(8, i=3)

    @vsc.constraint
    def kind_c(self):
        # Guards over non-rand state with multi-statement bodies, as in
        # riscv_instr's constraints.
        with vsc.if_then(self.kind.inside(vsc.rangelist(1, 2, 3))):
            self.rd != 0
            self.rs1 != 0
        with vsc.if_then(self.kind.inside(vsc.rangelist(200, 201))):
            self.rd == 2
            self.rs1 == 2


@vsc.randobj
class Stream:
    def __init__(self):
        self.avail_regs = vsc.randsz_list_t(vsc.rand_bit_t(5))

    @vsc.constraint
    def avail_c(self):
        self.avail_regs.size == 6
        vsc.unique(self.avail_regs)
        with vsc.foreach(self.avail_regs, idx=True) as i:
            self.avail_regs[i] > 2

    def gen(self, instr):
        with instr.randomize_with():
            with vsc.if_then(self.avail_regs.size > 0):
                with vsc.if_then(instr.has_rd):
                    instr.rd.inside(vsc.rangelist(self.avail_regs))
                instr.rs1.inside(vsc.rangelist(self.avail_regs))


class TestRiscvDvShapes(VscTestCase):

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_unrandomized_list_size_untouched(self):
        """An empty randsz list on an object never randomized keeps size 0."""
        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                s = Stream()            # never randomized: avail_regs stays empty
                for _ in range(10):
                    s.gen(Instr())
                m = s.avail_regs.get_model()
                self.assertEqual(int(m.size.get_val()), 0)
                self.assertEqual(len(s.avail_regs), 0)

    def test_inside_randsz_list_honoured(self):
        """`x.inside(rangelist(list))` over another object's populated randsz list."""
        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                s = Stream()
                s.randomize()
                regs = [int(r) for r in s.avail_regs]
                self.assertEqual(len(regs), 6)
                for _ in range(40):
                    it = Instr()
                    s.gen(it)
                    self.assertIn(int(it.rd), regs)
                    self.assertIn(int(it.rs1), regs)

    def test_inside_cosolved_randsz_list(self):
        """Membership in a randsz list whose size is solved in the same call."""
        @vsc.randobj
        class C:
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.rand_uint8_t())
                self.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                self.l.size in vsc.rangelist(vsc.rng(1, 4))
                with vsc.foreach(self.l, idx=True) as i:
                    self.l[i] < 50
                self.x.inside(vsc.rangelist(self.l))

        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                for _ in range(40):
                    o = C()
                    o.randomize()
                    self.assertIn(int(o.x), [int(v) for v in o.l])

    def test_state_guard_with_inside_folds(self):
        """A guard `kind inside {...}` over non-rand state picks its branch."""
        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                it = Instr()
                it.kind = 200
                for _ in range(10):
                    it.randomize()
                    self.assertEqual((int(it.rd), int(it.rs1)), (2, 2))
                it.kind = 1               # a changed guard value must not reuse the fold
                for _ in range(10):
                    it.randomize()
                    self.assertNotEqual(int(it.rd), 0)
                    self.assertNotEqual(int(it.rs1), 0)

    @unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
    def test_state_guard_stays_off_bvsat(self):
        """The folded guard keeps riscv-dv's instruction shape on the primary engine."""
        from vsc.model.solver import dvsolve_backend as dvb
        ctor.set_solver_backend("dv-solve")
        calls = []
        orig = dvb.DvSolveBackend._solve_via_bvsat

        def spy(self, *a, **k):
            calls.append(1)
            return orig(self, *a, **k)
        dvb.DvSolveBackend._solve_via_bvsat = spy
        self.addCleanup(setattr, dvb.DvSolveBackend, "_solve_via_bvsat", orig)
        it = Instr()
        it.kind = 2
        for _ in range(10):
            it.randomize()
        self.assertEqual(calls, [])

    def test_inside_val(self):
        """ExprInModel.val() agrees with the solver's membership."""
        from vsc.model.expr_in_model import ExprInModel
        from vsc.model.expr_literal_model import ExprLiteralModel
        from vsc.model.expr_range_model import ExprRangeModel
        from vsc.model.expr_rangelist_model import ExprRangelistModel
        lit = lambda v: ExprLiteralModel(v, False, 8)        # noqa: E731
        rl = ExprRangelistModel([lit(1), ExprRangeModel(lit(10), lit(20))])
        self.assertTrue(bool(ExprInModel(lit(1), rl).val()))
        self.assertTrue(bool(ExprInModel(lit(15), rl).val()))
        self.assertFalse(bool(ExprInModel(lit(5), rl).val()))
        self.assertTrue(bool(ExprInModel(lit(5), ExprRangelistModel([])).val()))

    def test_deepcopy_after_randomize(self):
        """riscv-dv deep-copies randomized objects; the copy randomizes on its own."""
        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                tmpl = Instr()
                tmpl.randomize()
                tmpl.randomize()             # second call: a cached plan exists
                for _ in range(5):
                    c = copy.deepcopy(tmpl)
                    c.randomize()
                    self.assertNotEqual(int(c.rd), 0)
                tmpl.randomize()             # and the original still works

    def test_deepcopy_shares_enum_metadata(self):
        """A copy shares its enum fields' EnumInfo (riscv-dv copies an
        instruction per generated instruction) and still randomizes."""
        from enum import IntEnum

        class Op(IntEnum):
            ADD = 0
            SUB = 1
            XOR = 5

        @vsc.randobj
        class E:
            def __init__(self):
                self.op = vsc.rand_enum_t(Op)
                self.kind = vsc.enum_t(Op)

            @vsc.constraint
            def c(self):
                self.op != Op.SUB

        for be in _backends():
            with self.subTest(backend=be):
                ctor.set_solver_backend(be)
                t = E()
                t.randomize()
                c = copy.deepcopy(t)
                fc, ft = object.__getattribute__(c, "op"), object.__getattribute__(t, "op")
                self.assertIs(fc.enum_i, ft.enum_i)
                self.assertIs(fc.get_model().enums, ft.get_model().enums)
                seen = set()
                for _ in range(30):
                    c.randomize()
                    self.assertIn(c.op, (Op.ADD, Op.XOR))
                    seen.add(c.op)
                self.assertEqual(seen, {Op.ADD, Op.XOR})

    @unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
    def test_enum_domain_distribution(self):
        """Enum bound domains come from a per-type template (one range when the
        values are contiguous); dv-solve's marginals stay uniform through the
        solver."""
        import collections
        from enum import IntEnum

        class Run(IntEnum):
            A = 0
            B = 1
            C = 2
            D = 3
            E = 4

        @vsc.randobj
        class O:
            def __init__(self):
                self.r = vsc.rand_enum_t(Run)
                self.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                self.x < 10
                self.r != Run.C
                self.x != self.r

        ctor.set_solver_backend("dv-solve")
        n = 3000
        h = collections.Counter()
        for _ in range(n):
            o = O()
            o.randomize()
            h[int(o.r)] += 1
        self.assertEqual(set(h), {0, 1, 3, 4})
        for r in (0, 1, 3, 4):        # 9 values of x for every r: 1/4 each
            self.assertAlmostEqual(h[r] / n, 0.25, delta=0.04)

    @unittest.expectedFailure
    @unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
    def test_gapped_enum_ne_distribution(self):
        """KNOWN dv-solve defect, independent of the enum-domain template (same
        numbers before it): a gapped enum {0,1,2,10} with `!= 1` gives 0 about
        0.27 instead of 1/3. The same set as `x.inside(0, 2, 10)` is uniform.
        See doc/notes/riscv_dv_profile.md."""
        import collections
        from enum import IntEnum

        class Gap(IntEnum):
            A = 0
            B = 1
            C = 2
            D = 10

        @vsc.randobj
        class O:
            def __init__(self):
                self.g = vsc.rand_enum_t(Gap)
                self.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                self.x < 10
                self.g != Gap.B

        ctor.set_solver_backend("dv-solve")
        n = 6000
        h = collections.Counter()
        for _ in range(n):
            o = O()
            o.randomize()
            h[int(o.g)] += 1
        for g in (0, 2, 10):
            self.assertAlmostEqual(h[g] / n, 1 / 3, delta=0.03)

if __name__ == "__main__":
    unittest.main()
