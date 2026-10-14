"""Phase F / T-F2a — dv-solve serves `solve_order` RandSets natively.

Before F-2a, an order-bearing RandSet (`rs.rand_order_l` set) that the primary
bounds engine couldn't decide was proved SAT by BV-SAT and then *deferred for
serving* to Boolector (`reason_code="bvsat-sat-deferred"`) — the uniform sampler
has no notion of solve order. F-2a added **staged sampling** (`bvsat_sampler.
sample_ordered`): per order stage, pin a random domain value and assert it (the
Boolector swizzler's assume→assert), so dv-solve serves the values itself and
honors the ordering's distribution.

These tests lock both halves:
  * **native serve** — the order-bearing RandSet defers *nothing*
    (no `bvsat-sat-deferred` in the tally);
  * **order semantics** — the canonical `c==0 -> a==0` shape with `a` solved
    first yields `a > 0` on *every* draw (the `test_before_and_after_lists`
    property), which a joint-uniform sample would violate ~50% of the time.

Skipped when the dv-solve native library is unavailable.
"""
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
import vsc.model.solver.dvsolve_backend as dvb
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveSolveOrderNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    @staticmethod
    def _ordered_obj():
        @vsc.randobj
        class my_c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(64)
                s.b = vsc.rand_bit_t(64)
                s.c = vsc.rand_bit_t(1)

            @vsc.constraint
            def abc_c(s):
                # Solving a (or b) first makes a==0 essentially impossible:
                # a is pinned to a random 64-bit value, forcing c != 0.
                with vsc.implies(s.c == 0):
                    s.a == 0
                    s.b == 0
        return my_c()

    def test_solve_order_served_natively(self):
        """The order-bearing RandSet must defer nothing — dv-solve serves it."""
        obj = self._ordered_obj()
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        try:
            for _ in range(40):
                with obj.randomize_with():
                    vsc.solve_order(obj.a, obj.c)
            hist = rnd.get_fallback_tally()
        finally:
            rnd.restore_fallback_tally(snap)
        deferred = {k: v for k, v in hist.items()
                    if k.split(":")[0] == "bvsat-sat-deferred"}
        self.assertEqual(
            deferred, {},
            "order-bearing RandSet deferred for serving instead of being served "
            "natively by staged sampling: %s" % hist)

    def test_solve_order_distribution(self):
        """Solving `a` before `c` must force `a > 0` on every draw (the order
        semantic; a joint-uniform sample would give a==0 ~half the time)."""
        obj = self._ordered_obj()
        samples = 80
        a_pos = 0
        for _ in range(samples):
            with obj.randomize_with():
                vsc.solve_order(obj.a, obj.c)
            if int(obj.a) > 0:
                a_pos += 1
        self.assertEqual(
            a_pos, samples,
            "solve_order(a, c) did not honor ordering: a>0 on %d/%d draws "
            "(expected all)" % (a_pos, samples))


    # ------------------------------------------------------------------ #
    # V18 — an ordered field wider than 64 bits                            #
    # ------------------------------------------------------------------ #
    # A stage's value was frozen with an int64 constant, so a wider ordered
    # field deferred (`bvsat-sat-deferred`). It is now frozen as one wide
    # constant, drawn from the field's own domain, not the int64 envelope
    # its `add_var` bounds are clamped to.

    def _strict_draws(self, obj, n, field="a"):
        saved = rnd._NO_FALLBACK
        rnd._NO_FALLBACK = True
        try:
            out = []
            for _ in range(n):
                obj.randomize()
                out.append(int(getattr(obj, field)))
            return out
        finally:
            rnd._NO_FALLBACK = saved

    def test_wide_order_served_and_honored(self):
        @vsc.randobj
        class wide_c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(128)
                s.c = vsc.rand_bit_t(8)

            @vsc.constraint
            def k(s):
                vsc.solve_order(s.a, s.c)
                with vsc.implies(s.c == 0):
                    s.a == 0
        vals = self._strict_draws(wide_c(), 40)
        self.assertTrue(all(v > 0 for v in vals), vals)
        # Drawn from the 128-bit domain, not the int64 envelope.
        self.assertTrue(any(v >= (1 << 64) for v in vals), vals)

    def test_wide_order_draws_inside_a_wide_bound(self):
        """`5 < a < 2**70` on 128 bits: the pin is drawn from the bound. Drawn
        from the whole 128-bit range, every target missed the bound, and each
        call paid 8 failed SAT checks before serving the stage with a plain
        uniform sample (about 9x slower). Only the final stage may use it."""
        from vsc.model.solver import bvsat_sampler

        @vsc.randobj
        class bounded_c(object):
            def __init__(s):
                s.a = vsc.rand_bit_t(128)
                s.c = vsc.rand_bit_t(8)

            @vsc.constraint
            def k(s):
                vsc.solve_order(s.a, s.c)
                s.a < (1 << 70)
                s.a > 5
                with vsc.implies(s.c == 0):
                    s.a == 0
        calls = []
        real = bvsat_sampler.sample

        def counting(make_base, readback, *a, **kw):
            calls.append([vid for (_f, vid) in readback])
            return real(make_base, readback, *a, **kw)
        bvsat_sampler.sample = counting
        try:
            vals = self._strict_draws(bounded_c(), 40)
        finally:
            bvsat_sampler.sample = real
        self.assertTrue(all(5 < v < (1 << 70) for v in vals), vals)
        self.assertGreater(len({v >> 64 for v in vals}), 8, vals)
        self.assertEqual(len(calls), len(vals),
                         "the `a` stage fell back to a uniform sample")

    def test_wide_signed_order(self):
        """A signed 100-bit ordered field pins negative values too."""
        @vsc.randobj
        class signed_c(object):
            def __init__(s):
                s.a = vsc.rand_int_t(100)
                s.c = vsc.rand_bit_t(8)

            @vsc.constraint
            def k(s):
                vsc.solve_order(s.a, s.c)
                with vsc.implies(s.c == 0):
                    s.a == 0
        vals = self._strict_draws(signed_c(), 40)
        self.assertTrue(all(-(1 << 99) <= v < (1 << 99) and v != 0
                            for v in vals), vals)
        self.assertTrue(any(v < -(1 << 64) for v in vals), vals)
        self.assertTrue(any(v > (1 << 64) for v in vals), vals)


if __name__ == "__main__":
    unittest.main()
