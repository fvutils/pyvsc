"""Phase F / EF-1a — native variable-indexed array select.

A subscript ``arr[idx]`` with a *rand* index used to defer to the Boolector net
(``reason_code="array"``, the largest `array` residual class). The dv-solve
translator now encodes it natively as an ITE chain over the active element set:

    ITE(idx==0, arr[0], ITE(idx==1, arr[1], ... arr[n-1]))

These tests lock three properties:

  1. **Strict-no-fallback serving.** With an empty fallback chain the
     variable-indexed-select shapes randomize green and defer *nothing*.
  2. **Correctness + index spread.** Every produced model satisfies the
     subscript constraint and the index ranges over its whole legal domain.
  3. **XCHECK parity.** With ``VSC_DVSOLVE_XCHECK`` forced on, Boolector accepts
     every dv-solve model — even for a *co-solved* index, which Boolector-as-
     *solver* gets wrong (it snapshots the index). XCHECK validates the finished
     model, when the index is concrete, so it agrees.

The genuinely-unsolvable shape (a co-solved index coupled so the snapshotted
element conflicts with another constraint) fails identically on dv-solve and
Boolector — a pre-existing pyvsc modeling limitation, not an EF-1a regression —
so it is documented but not asserted here.

Skipped when the dv-solve native library is unavailable.
"""
import random
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc.model.solver import xcheck
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@vsc.randobj
class _Select(object):
    # arr[idx] == val with a rand, in-range index. idx is bounded but otherwise
    # free, so it co-solves with the element across the corpus.
    def __init__(s):
        s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 4)
        s.idx = vsc.rand_uint8_t()
        s.val = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.idx < 4
        s.arr[s.idx] == s.val


# NB: a bare bound on the selected element alone (`arr[idx] < 10`, nothing else
# tying the array to idx) is NOT a robustly-solvable shape in pyvsc: the index is
# snapshotted and only one element co-solves, so the bound lands on a *baked
# constant* element whose current value may violate it -> spurious UNSAT. This
# fails identically on dv-solve and Boolector (verified), so it is a pre-existing
# modeling limitation, not an EF-1a serving case, and is deliberately not tested
# here. The robust shapes below either absorb the element into a free var
# (`==val`) or tie the whole array together (`argmax`).


@vsc.randobj
class _SelectArgmax(object):
    # arr[idx] >= every element -> idx must be an arg-max. Forces a genuinely
    # symbolic, relational select over the whole array.
    def __init__(s):
        s.arr = vsc.rand_list_t(vsc.rand_uint8_t(), 6)
        s.idx = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.idx < 6
        with vsc.foreach(s.arr, idx=True) as i:
            s.arr[s.idx] >= s.arr[i]


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveArraySelectNative(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def _no_fallback(self):
        """Force a strict, fallback-free posture for the duration of a test."""
        snap = rnd.snapshot_fallback_tally()
        rnd.set_fallback_tally(True)
        rnd.reset_fallback_tally()
        self.addCleanup(rnd.restore_fallback_tally, snap)

    # ------------------------------------------------------------------ #
    # EF-1a.1 — strict-no-fallback serving + correctness + index spread    #
    # ------------------------------------------------------------------ #
    def test_select_eq_native(self):
        self._no_fallback()
        obj = _Select()
        seen_idx = set()
        for i in range(80):
            random.seed(i)
            obj.randomize()
            arr = [int(x) for x in obj.arr]
            idx = int(obj.idx)
            seen_idx.add(idx)
            self.assertTrue(0 <= idx < 4)
            self.assertEqual(
                arr[idx], int(obj.val),
                "arr[idx] != val: idx=%d val=%d arr=%s" % (idx, int(obj.val), arr))
        self.assertEqual(seen_idx, {0, 1, 2, 3},
                         "index did not spread over its domain: %s" % seen_idx)
        self.assertEqual(rnd.get_fallback_tally(), {},
                         "variable-indexed select deferred to the net")

    def test_select_argmax_native(self):
        self._no_fallback()
        obj = _SelectArgmax()
        for i in range(60):
            random.seed(i)
            obj.randomize()
            arr = [int(x) for x in obj.arr]
            idx = int(obj.idx)
            self.assertEqual(
                arr[idx], max(arr),
                "arr[idx] is not the max: idx=%d arr=%s" % (idx, arr))
        self.assertEqual(rnd.get_fallback_tally(), {})

    # ------------------------------------------------------------------ #
    # EF-1a.2 — XCHECK parity (the soundness gate). Boolector validates     #
    # every dv-solve model, including the co-solved-index shapes.           #
    # ------------------------------------------------------------------ #
    def test_select_xcheck_parity(self):
        prev = xcheck.set_xcheck(True)
        self.addCleanup(xcheck.restore_xcheck, prev)
        xcheck.reset_tally()
        for cls in (_Select, _SelectArgmax):
            obj = cls()
            for i in range(40):
                random.seed(i)
                obj.randomize()
        tally = xcheck.get_tally()
        self.assertEqual(tally["mismatch"], 0,
                         "XCHECK mismatch on a native array select: %s" % tally)
        self.assertGreater(tally["checked"], 0,
                           "XCHECK checked nothing (oracle unavailable?): %s" % tally)


if __name__ == "__main__":
    unittest.main()
