"""Symbolic (rand) array-index select in the dataclass front-end — Workstream A.

`arr[idx]` with a *rand* index is a core PSS constraint shape. The dv-solve core
encodes it as a select over the array's elements; Workstream A (randset unification
in ``RandInfoBuilder``) makes *every* candidate element a free solver var — not just
the snapshot element — so arbitrary constraints on ``arr[idx]`` (bounds, arithmetic,
relational, two independent indices) co-solve with the index in a single solve.

These are **dv-solve** capabilities. Boolector-as-solver snapshots the index at
build time (``ExprArraySubscriptModel.build`` reads ``int(rhs.val())``) and cannot
co-solve a symbolic index, so the correctness tests skip on boolector. Boolector's
role is the XCHECK oracle: it validates the *finished* dv-solve model when the index
is concrete — locked by ``test_select_xcheck_parity``.

Parallels the classic gate ``ve/unit/test_dvsolve_array_select_native.py``; see
``doc/notes/dv_solve_symbolic_array_index_plan.md`` (Workstream A).
"""
import random

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.impl import ctor
import vsc.model.randomizer as rnd
from vsc.model.solve_failure import SolveFailure


class TestSymbolicArrayIndex(DcTestCase):

    # ---- helpers --------------------------------------------------------- #
    def _require_dvsolve(self):
        if ctor.get_solver_backend() != "dv-solve":
            self.skipTest("symbolic array select is a dv-solve capability "
                          "(boolector is the XCHECK oracle only)")

    def _no_fallback(self):
        """Assert a strict, fallback-free posture for the duration of a test."""
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        self.addCleanup(rnd.restore_fallback_tally, snap)

    # ---- A: correctness -------------------------------------------------- #
    def test_select_eq(self):
        # arr[idx] == val, rand in-range index + free companion. Index spreads its
        # whole domain, correctness holds, and it serves natively (no fallback).
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.arr[self.idx] == self.val

        c = my_c()
        seen = set()
        for i in range(80):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            seen.add(idx)
            self.assertTrue(0 <= idx < 4)
            self.assertEqual(arr[idx], int(c.val), (arr, idx, int(c.val)))
        self.assertEqual(seen, {0, 1, 2, 3}, "index did not spread: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "variable-indexed select deferred to the net")

    def test_select_bare_bound(self):
        # THE headline fix: arr[idx] < K with nothing else tying the array to idx.
        # Before Workstream A this was a SolveFailure (only arr[snapshot] was free,
        # the chosen arm was a baked constant). Now every arm is a free var.
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.arr[self.idx] < 10

        c = my_c()
        seen = set()
        for i in range(80):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            seen.add(idx)
            self.assertTrue(0 <= idx < 4)
            self.assertLess(arr[idx], 10, (arr, idx))
        self.assertEqual(seen, {0, 1, 2, 3}, "index did not spread: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {})

    def test_select_in_expr(self):
        # The selected element inside a bounded expression: arr[idx] + 5 == other,
        # other < 50. Also a SolveFailure before Workstream A.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()
            other: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.arr[self.idx] + 5 == self.other
                self.other < 50

        c = my_c()
        for i in range(60):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            self.assertEqual(arr[idx] + 5, int(c.other), (arr, idx, int(c.other)))
            self.assertLess(int(c.other), 50)

    def test_select_relational_two_indices(self):
        # Two independent rand indices related through the array: arr[i] > arr[j].
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=5)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 5
                self.j < 5
                self.arr[self.i] > self.arr[self.j]

        c = my_c()
        for k in range(60):
            random.seed(k)
            c.randomize()
            arr = [int(x) for x in c.arr]
            i, j = int(c.i), int(c.j)
            self.assertGreater(arr[i], arr[j], (arr, i, j))

    def test_select_two_indices_equal(self):
        # Two symbolic selects tied together: arr[i] == arr[j] with i != j — forces
        # a duplicate value at two solver-chosen positions.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=5)
            i: vdc.u8 = vdc.rand()
            j: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.i < 5
                self.j < 5
                self.i != self.j
                self.arr[self.i] == self.arr[self.j]

        c = my_c()
        for k in range(60):
            random.seed(k)
            c.randomize()
            arr = [int(x) for x in c.arr]
            i, j = int(c.i), int(c.j)
            self.assertNotEqual(i, j, (i, j))
            self.assertEqual(arr[i], arr[j], (arr, i, j))

    def test_select_argmax(self):
        # arr[idx] >= every element -> idx is an arg-max. A genuinely symbolic,
        # relational select over the whole array (index co-solves with the maximum).
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=6)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 6
                with vdc.foreach(self.arr, it=False, idx=True) as i:
                    self.arr[self.idx] >= self.arr[i]

        c = my_c()
        for k in range(60):
            random.seed(k)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            self.assertEqual(arr[idx], max(arr), (arr, idx))
        self.assertEqual(rnd.get_fallback_tally(), {})

    def test_select_medium_array_native(self):
        # A larger element count still serves natively (efficiency deep-dive is
        # Workstream B; this locks that the ITE encoding stays fallback-free here).
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=16)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 16
                self.arr[self.idx] == self.val

        c = my_c()
        seen = set()
        for i in range(120):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            seen.add(idx)
            self.assertEqual(arr[idx], int(c.val), (arr, idx, int(c.val)))
        self.assertEqual(seen, set(range(16)), "index did not spread: %s" % seen)
        self.assertEqual(rnd.get_fallback_tally(), {})

    def test_select_uses_native_path(self):
        # Workstream B: a small (n<=64) contiguous rand-element array must lower
        # through the native `expr_array_select` op (flat guard-reified select),
        # not the O(n) Python ITE chain. Lock that the native branch is actually
        # taken and still produces correct results, so a later refactor can't
        # silently regress to the ITE encoding.
        self._require_dvsolve()
        from vsc.model.solver import dvsolve_translator as _dt

        orig = _dt.DvSolveExprTranslator._try_native_array_select
        stats = {"native": 0, "fallback": 0}

        def _counting(self, e, arr, n, w, signed):
            r = orig(self, e, arr, n, w, signed)
            stats["native" if r is not None else "fallback"] += 1
            return r

        _dt.DvSolveExprTranslator._try_native_array_select = _counting
        self.addCleanup(setattr, _dt.DvSolveExprTranslator,
                        "_try_native_array_select", orig)

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=8)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 8
                self.arr[self.idx] == self.val

        c = my_c()
        for i in range(20):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            self.assertEqual(arr[int(c.idx)], int(c.val))
        self.assertGreater(stats["native"], 0,
                           "native expr_array_select was never emitted for n=8")
        self.assertEqual(stats["fallback"], 0,
                         "a contiguous small select fell back to the ITE chain")

    def test_select_large_array_sound(self):
        # Regression lock for the propagator side-table sizing bug: a symbolic
        # select emits ~2 propagators per array element from a *single*
        # constraint, but the dv-solve compiler sized prop_refs/guard_vars/
        # constraint_id by the constraint *count*. Past ~65 elements the tables
        # overflowed — guard tracking was silently dropped, so `arr[idx]==val`
        # was quietly not enforced (wrong answers, no fallback, no crash). A
        # 96-element array is well past that cliff; it must solve correctly and
        # still serve natively (fallback-free).
        self._require_dvsolve()
        self._no_fallback()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=96)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 96
                self.arr[self.idx] == self.val

        c = my_c()
        for i in range(40):
            random.seed(i)
            c.randomize()
            arr = [int(x) for x in c.arr]
            idx = int(c.idx)
            self.assertTrue(0 <= idx < 96)
            self.assertEqual(arr[idx], int(c.val), (idx, int(c.val)))
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "large select deferred (side-table overflow regressed?)")

    def test_select_huge_array_no_crash(self):
        # Regression lock for the decision-depth overflow: the search pushes one
        # level per decided variable, and a symbolic select frees every array
        # element, so an array larger than MAX_DECISION_DEPTH would overflow the
        # fixed decisions/level_marks arrays — an out-of-bounds write that
        # segfaulted the interpreter. The depth guard must degrade this to a
        # clean defer (SolveFailure at worst) instead of crashing the process.
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=400)
            idx: vdc.u16 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 400
                self.arr[self.idx] == self.val

        c = my_c()
        # The contract here is *survival*, not correctness: reaching the end of
        # the loop proves the engine never performed the out-of-bounds write.
        for i in range(5):
            random.seed(i)
            try:
                c.randomize()
            except SolveFailure:
                pass  # a clean defer is an acceptable outcome for this size

    # ---- soundness: UNSAT parity ----------------------------------------- #
    def test_select_unsat(self):
        # arr[idx] == 5 while every element is pinned to 0 -> genuinely UNSAT for
        # any in-range idx. Must fail (not silently mis-solve).
        self._require_dvsolve()

        @vdc.dataclass
        class my_c(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                with vdc.foreach(self.arr) as it:
                    it == 0
                self.arr[self.idx] == 5

        c = my_c()
        with self.assertRaises(SolveFailure):
            c.randomize()

    # ---- soundness: XCHECK parity (boolector validates dv-solve models) --- #
    def test_select_xcheck_parity(self):
        # With XCHECK forced on, Boolector validates every finished dv-solve model
        # (idx concrete at validation time), including the co-solved-index shapes.
        self._require_dvsolve()
        from vsc.model.solver import xcheck

        @vdc.dataclass
        class _Eq(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()
            val: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.arr[self.idx] == self.val

        @vdc.dataclass
        class _Bound(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=4)
            idx: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.idx < 4
                self.arr[self.idx] < 10

        prev = xcheck.set_xcheck(True)
        self.addCleanup(xcheck.restore_xcheck, prev)
        xcheck.reset_tally()
        for cls in (_Eq, _Bound):
            obj = cls()
            for i in range(40):
                random.seed(i)
                obj.randomize()
        tally = xcheck.get_tally()
        self.assertEqual(tally["mismatch"], 0,
                         "XCHECK mismatch on a symbolic array select: %s" % tally)
        self.assertGreater(tally["checked"], 0,
                           "XCHECK checked nothing (oracle unavailable?): %s" % tally)
