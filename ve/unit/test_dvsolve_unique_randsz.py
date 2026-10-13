"""V2 (fallback_elimination_v2_plan.md, bug B2) — ``unique`` over a random-sized
array whose size is co-solved in the same RandSet.

``_unique_randsz`` guards each element pair on the co-solved size, and read the
size's width as ``arr.size.width()``; ``width`` is an int attribute, so every
call raised ``TypeError`` (issue repro ``i203``), with or without the fallback.
The co-solved path had no test.

Skipped when the dv-solve native library is unavailable.
"""
import unittest
from contextlib import contextmanager

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
import vsc.model.randomizer as rnd
from vsc_test_case import VscTestCase


def _dvsolve_available():
    try:
        return select_backend("dv-solve").available()
    except Exception:
        return False


@contextmanager
def _strict_no_fallback():
    """VSC_DVSOLVE_NO_FALLBACK strict mode: a deferral raises instead of
    falling back to Boolector."""
    saved = rnd._NO_FALLBACK
    rnd._NO_FALLBACK = True
    try:
        yield
    finally:
        rnd._NO_FALLBACK = saved


@unittest.skipUnless(_dvsolve_available(), "dv-solve native library not available")
class TestDvSolveUniqueRandsz(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")

    def tearDown(self):
        ctor.set_solver_backend(None)
        super().tearDown()

    def test_i203_unique_with_foreach_cosolved_size(self):
        """i203: elements bounded by the co-solved size, and unique."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def l_c(s):
                s.l.size > 0
                s.l.size <= 5
                with vsc.foreach(s.l, it=True) as it:
                    it < s.l.size
                vsc.unique(s.l)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(500):
                obj.randomize()
                vals = list(obj.l)
                n = len(vals)
                self.assertTrue(1 <= n <= 5, n)
                self.assertEqual(len(set(vals)), n, vals)
                self.assertTrue(all(v < n for v in vals), vals)
                sizes.add(n)
        # The size is genuinely co-solved, not pinned to one value.
        self.assertGreater(len(sizes), 1, sizes)

    def test_unique_cosolved_size_slack_values(self):
        """More values than elements (``it < size + 2``, which also ties the
        size into the elements' RandSet): every size in range is reachable and
        the active prefix is always distinct."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.l = vsc.randsz_list_t(vsc.uint8_t())

            @vsc.constraint
            def l_c(s):
                s.l.size in vsc.rangelist((2, 4))
                with vsc.foreach(s.l, it=True) as it:
                    it < s.l.size + 2
                vsc.unique(s.l)

        obj = C()
        sizes = set()
        with _strict_no_fallback():
            for _ in range(200):
                obj.randomize()
                vals = list(obj.l)
                self.assertTrue(2 <= len(vals) <= 4, vals)
                self.assertEqual(len(set(vals)), len(vals), vals)
                self.assertTrue(all(v < len(vals) + 2 for v in vals), vals)
                sizes.add(len(vals))
        self.assertEqual(sizes, {2, 3, 4})


if __name__ == "__main__":
    unittest.main()
