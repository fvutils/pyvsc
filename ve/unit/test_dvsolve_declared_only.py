"""Stage 1 / Option A — declared-only bound gating on the dv-solve back-end.

On the dv-solve path the Randomizer runs the post-expansion VariableBoundVisitor
in ``declared_only`` mode: it skips constraint-propagation for **narrow**
(<=32-bit) fields under range inequalities (``< <= > >=``), letting the native
core re-derive those bounds, while KEEPING the propagators the native path can't
reconstruct or that its sampler needs:

  - ``==`` pins and ``inside`` / rangelist folds  — sole carrier of a wide literal
    or a bounds-only membership fold;
  - range propagators on WIDE (>32-bit) fields    — the wide sampler shows
    boundary bias unless handed the tightened domain.

These tests force ``derives_bounds`` on (independent of the env default) and lock
in both the mechanism and the correctness/distribution guarantees. A blanket
"skip ALL propagation" variant was validated and rejected — see
doc/notes/dv_solve_native_full_problem_plan.md (Stage 1 / Option A).

Skipped automatically when the dv-solve native library is unavailable.
"""
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solver.dvsolve_backend import DvSolveBackend
from vsc.visitors.variable_bound_visitor import (
    VariableBoundVisitor, _DECLARED_ONLY_NARROW_MAX_WIDTH)
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveDeclaredOnly(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        # Force the gate on regardless of the env default so this suite pins the
        # Option-A behavior directly.
        self._saved = DvSolveBackend.derives_bounds
        DvSolveBackend.derives_bounds = True

    def tearDown(self):
        DvSolveBackend.derives_bounds = self._saved
        ctor.set_solver_backend(None)
        super().tearDown()

    # ---- correctness carriers that must survive declared-only ----

    def test_wide_eq_pin_enforced(self):
        """A wide (64-bit) ``==`` to a literal is carried by the pinned domain
        (the literal can't round-trip int64 as a constraint), so the Eq
        propagator must be kept."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(64)

            @vsc.constraint
            def c(self):
                self.x == 0xFFFFFFFFFFFFFFFF

        it = W()
        for _ in range(10):
            it.randomize()
            self.assertEqual(int(it.x), 0xFFFFFFFFFFFFFFFF)

    def test_contiguous_rangelist_enforced(self):
        """A single contiguous ``inside`` range is an In fold; it must be kept
        (it is not always re-emitted as a translated membership constraint)."""
        @vsc.randobj
        class R(object):
            def __init__(self):
                self.x = vsc.rand_uint32_t()

            @vsc.constraint
            def c(self):
                self.x.inside(vsc.rangelist((1000, 2000)))

        it = R()
        for _ in range(200):
            it.randomize()
            self.assertTrue(1000 <= int(it.x) <= 2000, int(it.x))

    def test_gapped_membership_enforced(self):
        """A gapped set {0, 255} on a narrow field is an In fold — kept, and the
        top-of-set value must remain reachable."""
        @vsc.randobj
        class K(object):
            def __init__(self):
                self.k = vsc.rand_bit_t(8)

            @vsc.constraint
            def c(self):
                self.k.inside(vsc.rangelist(0, 255))

        it = K()
        seen = set()
        for _ in range(200):
            it.randomize()
            self.assertIn(int(it.k), (0, 255))
            seen.add(int(it.k))
        self.assertEqual(seen, {0, 255})

    # ---- distribution guarantees ----

    def test_wide_field_range_fair(self):
        """A wide (64-bit) field under ``value < K`` must stay bit-fair — the
        wide-field range propagator is kept so the sampler gets the tight
        domain (a full-width domain here would cluster near K-1)."""
        @vsc.randobj
        class W(object):
            def __init__(self):
                self.value = vsc.rand_bit_t(64)

            @vsc.constraint
            def c(self):
                self.value < (1 << 15)

        it = W()
        random.seed(0)
        ones = [0] * 15
        trials = 200
        for _ in range(trials):
            it.randomize()
            v = int(it.value)
            self.assertLess(v, 1 << 15)
            for b in range(15):
                ones[b] += (v >> b) & 1
        for b in range(15):
            self.assertTrue(
                70 <= ones[b] <= 130,
                "bit %d biased (%d/%d ones)" % (b, ones[b], trials))

    def test_narrow_array_distribution_uniform(self):
        """A narrow (u8) array element under a two-sided range is the skipped
        case; its distribution must remain broad/uniform over the feasible
        span (native re-derivation + uniform narrow sampler)."""
        @vsc.randobj
        class A(object):
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

            @vsc.constraint
            def c(self):
                with vsc.foreach(self.arr) as it:
                    it > 2
                    it < 250

        it = A()
        random.seed(0)
        vals = []
        for _ in range(200):
            it.randomize()
            vals.extend(int(x) for x in it.arr)
        for v in vals:
            self.assertTrue(3 <= v <= 249)
        mean = sum(vals) / len(vals)
        # Feasible midpoint is 126; a broad sampler lands near it. A collapsed
        # or boundary-biased sampler would miss this band badly.
        self.assertTrue(100 <= mean <= 152, "array mean %.1f not broad" % mean)
        self.assertGreater(max(vals), 240)
        self.assertLess(min(vals), 15)

    # ---- mechanism: the gate skips narrow ranges, keeps the rest ----

    def test_gate_skips_narrow_keeps_wide_and_folds(self):
        """Directly assert the propagator-selection rule on a mixed model."""
        @vsc.randobj
        class M(object):
            def __init__(self):
                self.n = vsc.rand_uint8_t()      # narrow, range -> skipped
                self.w = vsc.rand_bit_t(64)       # wide, range   -> kept
                self.p = vsc.rand_uint32_t()      # narrow, ==     -> kept (Eq)

            @vsc.constraint
            def c(self):
                self.n > 5
                self.n < 200
                self.w < (1 << 40)
                self.p == 1234

        it = M()
        fm = it.get_model()
        cons = list(fm.constraint_model_l)

        # declared_only ON: narrow range vars keep declared width; wide range and
        # == pinned vars are tightened.
        vbv_on = VariableBoundVisitor()
        vbv_on.process([fm], cons, False, declared_only=True)
        by_name = {f.name: b for f, b in vbv_on.bound_m.items()}
        self.assertLessEqual(_DECLARED_ONLY_NARROW_MAX_WIDTH, 32)
        # narrow 'n' NOT tightened: still spans its declared [0, 255]
        self.assertEqual(by_name["n"].domain.range_l[0][0], 0)
        self.assertEqual(by_name["n"].domain.range_l[-1][1], 255)
        # wide 'w' tightened by its range propagator (max < 2**40)
        self.assertLess(by_name["w"].domain.range_l[-1][1], (1 << 40))
        # '==' pin kept
        self.assertEqual(by_name["p"].domain.range_l[0][0], 1234)
        self.assertEqual(by_name["p"].domain.range_l[-1][1], 1234)

        # declared_only OFF: narrow 'n' IS tightened (baseline behavior).
        vbv_off = VariableBoundVisitor()
        vbv_off.process([fm], cons, False, declared_only=False)
        by_name_off = {f.name: b for f, b in vbv_off.bound_m.items()}
        self.assertEqual(by_name_off["n"].domain.range_l[0][0], 6)
        self.assertEqual(by_name_off["n"].domain.range_l[-1][1], 199)


if __name__ == "__main__":
    unittest.main()
