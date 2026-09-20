"""Bulk readback (Stage 1 / S1.2): ``solver_get_values`` must agree with the
per-element ``solver_get_value`` loop it replaces, exactly, for every width and
signedness — including the cases where a sign-extension or masking bug would
hide.

The readback path is the one place where a wrong answer is *silent*: the solve
succeeded, the constraints were satisfied, and only the value that reached the
field is wrong. So the equivalence is tested directly against the scalar reader
on a live solved ctx, not just inferred from suite results.

See ``doc/notes/vdc_stage1_impl_plan.md`` §S1.2 and
``benchmarks/RESULTS_stage1.md``.
"""
import ctypes
import random
import unittest

import vsc
from vsc_test_case import VscTestCase

try:
    from vsc.model.solver.dvsolve_backend import DvSolveBackend, _BulkReadback
    _HAVE = DvSolveBackend.available()
except Exception:                                   # pragma: no cover
    _HAVE = False


@unittest.skipUnless(_HAVE, "dv-solve not available")
class TestBulkReadback(VscTestCase):

    # ------------------------------------------------------------------ #
    # Equivalence against the scalar reader, on a real solved ctx
    # ------------------------------------------------------------------ #

    def _solved_ctx(self, specs):
        """Build+solve a problem with one var per ``(width, signed, lo, hi)``.
        Returns ``(ctx, [(vid, width, signed)])``."""
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import SOLVE_OK
        from vsc.model.solver.dvsolve_backend import _make_solve_ctx

        b = SolveProblemBuilder()
        try:
            vids = []
            for i, (w, signed, lo, hi) in enumerate(specs):
                b.add_var(i, w, signed, lo, hi)
                vids.append((i, w, signed))
            buf, sz = b.finalize()
        finally:
            b.destroy()
        ctx = _make_solve_ctx(buf, sz)
        self.assertEqual(SOLVE_OK, ctx.solve(seed=12345, fair_pick=True))
        return ctx, vids

    def _check_equivalent(self, specs):
        ctx, vids = self._solved_ctx(specs)
        try:
            scalar = [ctx.get_value(vid) for vid, _w, _s in vids]

            n = len(vids)
            ids = (ctypes.c_uint32 * n)(*[v for v, _w, _s in vids])
            out = (ctypes.c_int64 * n)()
            ctx.get_values(ids, out, n)
            bulk = memoryview(out).cast('B').cast('q').tolist()

            self.assertEqual(scalar, bulk,
                             "bulk readback disagrees with scalar for %r" % (specs,))

            # ...and the width/sign reinterpretation on top must match too.
            as_field = DvSolveBackend._as_field_value
            self.assertEqual(
                [as_field(v, w, s) for v, (_vid, w, s) in zip(scalar, vids)],
                [as_field(v, w, s) for v, (_vid, w, s) in zip(bulk, vids)])
        finally:
            ctx.destroy()

    def test_widths_unsigned(self):
        for w in (1, 8, 32, 63, 64):
            with self.subTest(width=w):
                hi = (1 << w) - 1
                self._check_equivalent([(w, False, 0, hi)] * 4)

    def test_widths_signed(self):
        for w in (8, 32, 63, 64):
            with self.subTest(width=w):
                lo, hi = -(1 << (w - 1)), (1 << (w - 1)) - 1
                self._check_equivalent([(w, True, lo, hi)] * 4)

    def test_width64_unsigned_top_bit(self):
        """The case the masking exists for: a u64 whose value has bit 63 set
        comes back from the solver as a negative int64."""
        lo = 1 << 63
        self._check_equivalent([(64, False, lo, (1 << 64) - 1)] * 4)

    def test_mixed_widths_and_signs(self):
        self._check_equivalent([
            (1, False, 0, 1),
            (8, True, -128, 127),
            (16, False, 0, 65535),
            (64, True, -(1 << 63), (1 << 63) - 1),
            (64, False, 1 << 63, (1 << 64) - 1),
            (32, False, 0, (1 << 32) - 1),
        ])

    def test_single_element(self):
        self._check_equivalent([(8, False, 0, 255)])

    # ------------------------------------------------------------------ #
    # _BulkReadback's own mask precomputation
    # ------------------------------------------------------------------ #

    class _FakeField(object):
        __slots__ = ("v",)

        def set_val(self, v):
            self.v = v

    def _bulk_for(self, entries):
        return _BulkReadback([(self._FakeField(), vid, w, s)
                              for (vid, w, s) in entries])

    def test_uniform_mask_detected(self):
        """The common case — an array of one unsigned type — must collapse to a
        single mask, since that is what the hot loop is specialised for."""
        b = self._bulk_for([(i, 8, False) for i in range(16)])
        self.assertEqual(255, b.uniform_mask)

    def test_uniform_none_mask_for_all_signed(self):
        b = self._bulk_for([(i, 32, True) for i in range(4)])
        self.assertIsNone(b.uniform_mask)

    def test_mixed_masks_fall_back(self):
        b = self._bulk_for([(0, 8, False), (1, 32, True), (2, 16, False)])
        self.assertIs(False, b.uniform_mask)
        self.assertEqual([255, None, 65535], b.masks)

    def test_read_into_fields_matches_as_field_value(self):
        """End-to-end: _BulkReadback must produce exactly what the scalar loop
        with _as_field_value produced."""
        specs = [(1, False, 0, 1), (8, True, -128, 127),
                 (64, False, 1 << 63, (1 << 64) - 1), (32, False, 0, 4095)]
        ctx, vids = self._solved_ctx(specs)
        try:
            expect = [DvSolveBackend._as_field_value(ctx.get_value(vid), w, s)
                      for (vid, w, s) in vids]
            b = self._bulk_for(vids)
            b.read_into_fields(ctx)
            self.assertEqual(expect, [f.v for f in b.fields])
        finally:
            ctx.destroy()

    # ------------------------------------------------------------------ #
    # The switch itself
    # ------------------------------------------------------------------ #

    def test_kill_switch_gives_identical_results(self):
        """With the same seed, bulk and scalar readback must produce the same
        stimulus — the switch is a performance switch, not a behavioural one."""
        from vsc.model import opt_flags

        @vsc.randobj
        class Item(object):
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.uint8_t(), 24)
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_int_t(32)

            @vsc.constraint
            def c(self):
                with vsc.foreach(self.arr) as it:
                    it > 2
                    it < 250
                self.a < 1000
                self.b > -50

        def run(bulk):
            saved = opt_flags.BULK_READBACK
            opt_flags.BULK_READBACK = bulk
            try:
                random.seed(7)
                vsc.random.seed(7)
                it = Item()
                out = []
                for _ in range(12):            # >1 solve: exercises plan reuse
                    it.randomize()
                    out.append((list(it.arr), it.a, it.b))
                return out
            finally:
                opt_flags.BULK_READBACK = saved

        on, off = run(True), run(False)
        self.assertEqual(off, on)
        for arr, a, b in on:
            self.assertTrue(all(2 < v < 250 for v in arr))
            self.assertLess(a, 1000)
            self.assertGreater(b, -50)


if __name__ == "__main__":
    unittest.main()
