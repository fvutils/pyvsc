"""Phase C — native arrays / ``foreach`` / aggregates on the dv-solve back-end.

These tests assert that array constructs are handled *natively* by dv-solve (the
primary bounds-propagation engine, not the Boolector fallback). Each randomization
runs under a "no-fallback" guard that makes any fall-through to Boolector raise, so
a regression that re-introduces a defer fails loudly here rather than passing
quietly through the oracle.

Coverage (filled in as Phase C lands):
  * T-C0  baseline: fixed-size ``foreach`` + per-element constraints solve natively,
          including the all-different idiom unblocked by the constant-guard fold
          (C-0b). This is the regression floor every later sub-step builds on.
  * T-C2  fixed-size ``sum`` (native ``expr_sum``) and ``product`` (mul chain).
  * T-C3  ``sum`` width parity vs Boolector + the mixed-width equality fix that
          C-2 surfaced (a wide aggregate compared to a narrow comparand must not
          wrap at the narrow width).
  * T-C4  ``unique`` over a fixed-size array (pairwise ``!=``) and over a
          *random-sized* array (size-guarded active prefix — Phase F arrays
          burn-down, the dominant remaining ``array`` residual).

See doc/notes/dv_solve_phaseC_arrays_plan.md. Skipped when the dv-solve native
library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _no_fallback():
    """Make any fall-through to the Boolector back-end raise, so an array construct
    that is *not* handled natively by dv-solve fails the test instead of being
    served by the oracle."""
    import vsc.model.solver.boolector_backend as bb
    orig = bb.BoolectorBackend.solve_randset

    def _raise(self, rs, *a, **k):
        raise AssertionError(
            "dv-solve fell back to Boolector for a RandSet (array not native?)")

    bb.BoolectorBackend.solve_randset = _raise
    try:
        yield
    finally:
        bb.BoolectorBackend.solve_randset = orig


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveArrayNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    # ------------------------------------------------------------------ #
    # T-C0 — fixed-size foreach baseline (no fallback)                     #
    # ------------------------------------------------------------------ #

    def test_tc0_foreach_per_element(self):
        """A per-element ``foreach`` bound constraint solves natively over N draws."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 8)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr, idx=True) as i:
                    s.arr[i] < 10

        c = C()
        with _no_fallback():
            for _ in range(50):
                c.randomize()
                self.assertTrue(all(int(x) < 10 for x in c.arr),
                                "element out of range: %s" % [int(x) for x in c.arr])

    def test_tc0_foreach_all_different(self):
        """The fixed-size all-different idiom (nested ``foreach`` + ``implies(i!=j)``)
        solves natively. This is the case the constant-guard fold (C-0b) unblocked:
        ``foreach`` substitutes the index with a literal, so the guard ``i != j``
        becomes a constant the translator now folds rather than emitting a
        disjunction the bounds engine can't serve."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 4)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr, idx=True) as i:
                    with vsc.foreach(s.arr, idx=True) as j:
                        with vsc.implies(i != j):
                            s.arr[i] != s.arr[j]

        c = C()
        with _no_fallback():
            for _ in range(50):
                c.randomize()
                vals = [int(x) for x in c.arr]
                self.assertEqual(len(set(vals)), len(vals),
                                 "not all-different: %s" % vals)

    def test_tc0_foreach_if_else_const_guard(self):
        """A ``foreach`` body with an index-dependent ``if_then`` (constant after
        index substitution) solves natively — the fold applies to both branches of
        an if/else, not just bare ``implies``."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 6)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr, idx=True) as i:
                    with vsc.if_then(i == 0):
                        s.arr[i] == 1
                    with vsc.else_then:
                        s.arr[i] == 5

        c = C()
        with _no_fallback():
            for _ in range(20):
                c.randomize()
                vals = [int(x) for x in c.arr]
                self.assertEqual(vals[0], 1, "arr[0] should be 1: %s" % vals)
                self.assertTrue(all(v == 5 for v in vals[1:]),
                                "arr[1:] should be 5: %s" % vals)


    # ------------------------------------------------------------------ #
    # T-C2 — fixed-size aggregates (sum native, product mul-chain)         #
    # ------------------------------------------------------------------ #

    def test_tc2_fixed_sum(self):
        """``arr.sum`` over a fixed-size array, bounded both sides, solves natively
        via the n-ary ``expr_sum`` propagator."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_bit_t(8), 16)

            @vsc.constraint
            def c(s):
                s.arr.sum > 0
                s.arr.sum < 40

        c = C()
        with _no_fallback():
            for _ in range(50):
                c.randomize()
                tot = sum(int(x) for x in c.arr)
                self.assertTrue(0 < tot < 40, "sum out of range: %d" % tot)

    def test_tc2_sum_eq_scalar(self):
        """``arr.sum == scalar`` (an equality whose sum side is wider than the
        comparand) solves natively and exactly — the mixed-width equality must not
        wrap the wide sum at the narrow comparand's width."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.main = vsc.rand_uint8_t()
                s.total = vsc.rand_uint8_t()
                s.sub = vsc.rand_list_t(vsc.rand_uint8_t(), 10)

            @vsc.constraint
            def c(s):
                s.total == 50
                with vsc.foreach(s.sub) as it:
                    it != 0
                s.main + s.sub.sum == s.total

        c = C()
        with _no_fallback():
            for _ in range(40):
                c.randomize()
                sub = [int(x) for x in c.sub]
                self.assertTrue(all(v != 0 for v in sub), "element is 0: %s" % sub)
                self.assertEqual(int(c.main) + sum(sub), 50,
                                 "sum equality wrapped: main=%d sub=%s" %
                                 (int(c.main), sub))

    def test_tc2_fixed_product(self):
        """``arr.product`` over a fixed-size array solves natively via a BIN_MUL
        chain."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_bit_t(8), 8)

            @vsc.constraint
            def c(s):
                s.arr.product == 4

        c = C()
        with _no_fallback():
            for _ in range(20):
                c.randomize()
                prod = 1
                for x in c.arr:
                    prod = (prod * int(x)) & ((1 << 63) - 1)
                self.assertEqual(prod, 4, "product != 4: %s" % [int(x) for x in c.arr])

    # ------------------------------------------------------------------ #
    # T-C3 — sum width parity vs Boolector (no silent overflow)            #
    # ------------------------------------------------------------------ #

    def test_tc3_sum_width_parity(self):
        """The native sum result width follows pyvsc's get_sum_width()
        (elem_w + clog2(n)), so a sum that fits there must be served bit-exactly
        and never silently overflow. Cross-check the served sum against the
        elements over N draws."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                # 8 x 32-bit elements -> sum width 35; constrain to a wide target.
                s.arr = vsc.rand_list_t(vsc.rand_bit_t(32), 8)

            @vsc.constraint
            def c(s):
                s.arr.sum <= 4096

        c = C()
        with _no_fallback():
            for _ in range(40):
                c.randomize()
                self.assertLessEqual(sum(int(x) for x in c.arr), 4096,
                                     "sum exceeded bound (overflow?)")


    # ------------------------------------------------------------------ #
    # T-C1 — constant-index element references (subscript / indexed field) #
    # ------------------------------------------------------------------ #

    def test_tc1_const_subscript(self):
        """A constant-index subscript (``l[1] == l[0] + 1``) resolves to the
        concrete element and solves natively (the const-index resolution path).
        Uses the list idiom pyvsc supports for direct subscripts."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def c(s):
                s.l.size == 4
                s.l[1] == s.l[0] + 1

        c = C()
        with _no_fallback():
            for _ in range(20):
                c.randomize()
                self.assertEqual(int(c.l[1]), int(c.l[0]) + 1,
                                 "subscript relation violated: %s" %
                                 [int(x) for x in c.l])

    def test_tc1_object_array_indexed_fieldref(self):
        """An object-array element field accessed through a ``foreach`` index
        (``c1[i].x == c2[i].y``) resolves to the concrete field and solves
        natively (the ExprIndexedFieldRefModel const-resolution path)."""
        @vsc.randobj
        class Item(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.a = vsc.rand_list_t(vsc.attr(Item()), 4)
                s.b = vsc.rand_list_t(vsc.attr(Item()), 4)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.a, idx=True) as i:
                    s.a[i].x == s.b[i].x
                    s.a[i].x < 50

        c = C()
        with _no_fallback():
            for _ in range(20):
                c.randomize()
                for i in range(4):
                    self.assertEqual(int(c.a[i].x), int(c.b[i].x))
                    self.assertLess(int(c.a[i].x), 50)

    # ------------------------------------------------------------------ #
    # T-C4 — unique over a fixed-size array                                #
    # ------------------------------------------------------------------ #

    def test_tc4_unique_over_array(self):
        """``unique`` over a fixed-size array expands to pairwise ``!=`` over the
        element fields and solves natively."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 5)

            @vsc.constraint
            def c(s):
                vsc.unique(s.arr)
                with vsc.foreach(s.arr, idx=True) as i:
                    s.arr[i] < 20

        c = C()
        with _no_fallback():
            for _ in range(30):
                c.randomize()
                v = [int(x) for x in c.arr]
                self.assertEqual(len(set(v)), len(v), "not unique: %s" % v)
                self.assertTrue(all(x < 20 for x in v), "out of range: %s" % v)

    def test_tc4_unique_over_randsz_array(self):
        """``unique`` over a *random-sized* array is served natively by the
        size-guarded encoding (Phase F arrays burn-down): only the active prefix
        ``[0:size]`` must be distinct. This was the dominant remaining ``array``
        residual (the ``test_list_scalar`` transitive idiom). serve-SAT is forced
        on so the co-solved-size guarded form (which routes to BV-SAT) serves in
        process; the resolved-size form serves from the primary regardless."""
        import vsc.model.solver.dvsolve_backend as dvb

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.rand_uint8_t())

            @vsc.constraint
            def c(s):
                s.l.size == 4
                with vsc.foreach(s.l, idx=True, it=False) as i:
                    s.l[i] < 6
                vsc.unique(s.l)

        saved = dvb._BVSAT_SERVE_SAT_MODE
        dvb._BVSAT_SERVE_SAT_MODE = "on"
        try:
            with _no_fallback():
                c = C()
                for _ in range(40):
                    c.randomize()
                    v = [int(x) for x in c.l]
                    self.assertEqual(len(v), 4, "active size != 4: %s" % v)
                    self.assertEqual(len(set(v)), len(v),
                                     "active prefix not unique: %s" % v)
                    self.assertTrue(all(x < 6 for x in v), "out of range: %s" % v)
        finally:
            dvb._BVSAT_SERVE_SAT_MODE = saved


    # ------------------------------------------------------------------ #
    # T-C3r — random-sized array sum (resolved-size prefix)                #
    # ------------------------------------------------------------------ #

    def test_tc3_randsz_sum(self):
        """``arr.sum`` over a random-sized array solves natively. pyvsc solves the
        array's ``size`` in an earlier RandSet (dependency order), so by the time
        the element RandSet carrying the sum is translated, ``size`` is a resolved
        constant and the active prefix is fixed. The sum must equal the target over
        the solver-chosen size, with the size itself varying across draws."""
        @vsc.randobj
        class C(object):
            def __init__(s, n):
                s.n = n                                   # non-rand target
                s.sz = vsc.rand_uint8_t(0)
                s.g = vsc.randsz_list_t(vsc.rand_uint8_t())

            @vsc.constraint
            def c(s):
                s.sz > 0
                s.sz < s.n
                s.g.size == s.sz
                with vsc.foreach(s.g, idx=True, it=False) as i:
                    s.g[i] > 0
                    s.g[i] <= s.n
                s.g.sum == s.n

        c = C(8)
        sizes = set()
        with _no_fallback():
            for _ in range(40):
                c.randomize()
                vals = [int(x) for x in c.g]
                sizes.add(len(vals))
                self.assertTrue(all(v > 0 for v in vals), "element <= 0: %s" % vals)
                self.assertEqual(sum(vals), 8,
                                 "randsz sum != target over active prefix: %s" % vals)

    # ------------------------------------------------------------------ #
    # C-5 — no-fallback residue: the enumerated remaining defers carry the #
    #       "array" reason code (not a silent superset).                   #
    # ------------------------------------------------------------------ #

    def test_c5_inside_over_array_native(self):
        """``a inside arr`` (membership over an array's elements) solves natively
        — expanded to OR_i (a == arr[i]) — with no fall-through to Boolector, and
        the membership holds on every draw."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 3)
                s.a = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.a.inside(s.arr)

        with _no_fallback():
            c = C()
            for _ in range(30):
                c.randomize()
                self.assertIn(int(c.a), [int(x) for x in c.arr],
                              "a inside arr violated: a=%d arr=%s" %
                              (int(c.a), [int(x) for x in c.arr]))

    def test_c5b_oversized_array_sum_still_defers(self):
        """A genuinely-unsupported array construct (a ``sum`` over more elements
        than the native n-ary summand cap) still defers with reason_code=="array"
        under strict mode — i.e. unsupported shapes fail loudly, not silently."""
        import vsc.model.randomizer as rnd
        from vsc.model.solver.backend import BackendIncomplete

        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 100)  # > 64-summand cap

            @vsc.constraint
            def c(s):
                s.arr.sum < 50

        saved = rnd._NO_FALLBACK
        rnd._NO_FALLBACK = True
        try:
            with self.assertRaises(BackendIncomplete) as ctx:
                C().randomize()
            self.assertEqual(getattr(ctx.exception, "reason_code", None), "array",
                             "defer should carry reason_code='array': %s" %
                             ctx.exception)
        finally:
            rnd._NO_FALLBACK = saved


if __name__ == "__main__":
    unittest.main()
