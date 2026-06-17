"""Native soft-constraint serving on the dv-solve primary path.

Locks the DSE-0 fix: guarded (conditional) softs `if_then(g): soft(e)` lower to the
disjunction soft `(!g)||e` and are honored by the dv-solve *primary* engine — no
Boolector fallback, no silent drop. The prior "0/20" was a pyvsc translator memo-key
bug (`_soft_ctx` missing from the memo key), fixed in dvsolve_translator.translate.

Run under strict no-fallback + serve-SAT so any regression that re-introduced a defer
(or dropped the soft) fails here rather than silently leaning on the net. XCHECK
(`VSC_DVSOLVE_XCHECK=1`) validates the served model against Boolector.

See doc/notes/dv_solve_soft_constraints_engine_plan.md (DSE-0/DSE-3).
"""
import os
import unittest

import vsc

_STRICT = {
    "VSC_SOLVER": "dvsolve",
    "VSC_DVSOLVE_NO_FALLBACK": "1",
    "VSC_DVSOLVE_BVSAT_SERVE_SAT": "on",
}


class TestDvSolveSoftNative(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _STRICT}
        os.environ.update(_STRICT)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_guarded_soft_honored_native(self):
        """`if_then(a>5): soft(d==40)` with `a>10` hard (guard always true) → the
        kept disjunction must satisfy d==40 every time, served on the primary path."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.d = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a > 10
                with vsc.if_then(s.a > 5):
                    vsc.soft(s.d == 40)

        it = It()
        for _ in range(50):
            it.randomize()
            self.assertGreater(int(it.a), 10)
            self.assertEqual(int(it.d), 40,
                             "guarded soft d==40 not honored natively")

    def test_guarded_soft_relaxes_when_conflicting(self):
        """When the guarded soft conflicts with a hard constraint, the engine must
        *relax* it (drop the preference) and still produce a valid model — the soft
        is never enforced as hard."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.a = vsc.rand_uint8_t()
                s.d = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.a > 10
                s.d == 7              # hard: d is pinned, conflicts with soft d==40
                with vsc.if_then(s.a > 5):
                    vsc.soft(s.d == 40)

        it = It()
        for _ in range(20):
            it.randomize()
            self.assertEqual(int(it.d), 7, "hard must win; soft must relax")

    def test_unconditional_soft_honored_native(self):
        """A plain `soft(e==50)` on an otherwise-free field is honored natively."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.e = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                vsc.soft(s.e == 50)

        it = It()
        for _ in range(20):
            it.randomize()
            self.assertEqual(int(it.e), 50)

    def test_soft_honored_on_bvsat_serve_path(self):
        """DSE-2: a soft coupled into a RandSet that *force-serves via BV-SAT* (a
        conjunctive guard body routes it to the complete engine) is honored by the
        engine's soft-aware MaxSAT serve — not silently dropped. Before DSE-2 this
        was honored ~random (the soft-less serve path)."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.g = vsc.rand_uint8_t()
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.g == 1
                with vsc.if_then(s.g == 1):   # conjunctive body → requires_bvsat
                    s.a < 200
                    s.b < 200
                vsc.soft(s.a == 40)

        it = It()
        for _ in range(30):
            it.randomize()
            self.assertEqual(int(it.a), 40,
                             "soft a==40 not honored on the BV-SAT serve path")

    def test_soft_relaxed_on_bvsat_serve_when_conflicting(self):
        """A soft that conflicts with a hard on the force-served path is relaxed by
        the engine's MaxSAT — the hard wins, the model stays valid."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.g = vsc.rand_uint8_t()
                s.a = vsc.rand_uint8_t()
                s.b = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.g == 1
                with vsc.if_then(s.g == 1):
                    s.a < 200
                    s.b < 200
                s.a == 50               # hard
                vsc.soft(s.a == 40)     # conflicts with the hard → must relax

        it = It()
        for _ in range(20):
            it.randomize()
            self.assertEqual(int(it.a), 50, "hard must win; conflicting soft relaxed")

    # ---- DSE-3: priority fidelity (relaxation order matches Boolector) ----
    #
    # pyvsc soft priority is *declaration order*: each soft in a block gets an
    # increasing priority value (`rand_info_builder._soft_priority`), and both
    # back-ends keep the *highest* priority value hardest (Boolector sorts
    # descending and asserts greedily, `boolector_backend.py:77`; dv-solve maps the
    # same `-priority` rank to dv priority 0 = keep-hardest,
    # `dvsolve_backend.py:444`). So among mutually-conflicting softs the
    # **last-declared wins** and earlier ones drop in declaration order — the
    # standard SystemVerilog soft-override semantics. These ladders assert that
    # forced outcome on BOTH the primary and the BV-SAT serve path; XCHECK
    # validates the served model against Boolector on top.

    def test_soft_priority_ladder_primary(self):
        """Three mutually-conflicting softs at distinct (declaration-order)
        priorities: the last-declared (highest priority) is kept, the earlier two
        relax. Primary path."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                vsc.soft(s.x == 1)   # priority 0 -> dropped
                vsc.soft(s.x == 2)   # priority 1 -> dropped
                vsc.soft(s.x == 3)   # priority 2 (last) -> kept

        it = It()
        for _ in range(30):
            it.randomize()
            self.assertEqual(int(it.x), 3,
                             "last-declared (highest-priority) soft must win")

    def test_soft_priority_ladder_hard_forces_drop(self):
        """A hard constraint that conflicts with the top-priority soft forces it to
        relax; the next-highest compatible soft is then kept. Verifies the engine
        relaxes in priority order AND that a hard always beats a soft."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.x != 3                 # hard: kills the top-priority soft
                vsc.soft(s.x == 1)       # priority 0 -> dropped
                vsc.soft(s.x == 2)       # priority 1 -> kept (top compatible)
                vsc.soft(s.x == 3)       # priority 2 -> conflicts with hard, dropped

        it = It()
        for _ in range(30):
            it.randomize()
            self.assertNotEqual(int(it.x), 3, "hard x!=3 must hold")
            self.assertEqual(int(it.x), 2,
                             "next-priority compatible soft (x==2) must be kept")

    def test_soft_priority_ladder_bvsat_serve(self):
        """The same priority ladder on a RandSet that *force-serves via BV-SAT* (a
        conjunctive guard body). Serve-path relaxation order must equal the primary
        order: last-declared soft kept, earlier ones relaxed."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.g = vsc.rand_uint8_t()
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                s.g == 1
                with vsc.if_then(s.g == 1):   # 2-stmt body -> requires_bvsat
                    s.x < 200
                    s.y < 200
                vsc.soft(s.x == 1)   # priority 0 -> dropped
                vsc.soft(s.x == 2)   # priority 1 -> dropped
                vsc.soft(s.x == 3)   # priority 2 (last) -> kept

        it = It()
        for _ in range(30):
            it.randomize()
            self.assertEqual(int(it.g), 1)
            self.assertEqual(int(it.x), 3,
                             "serve-path soft order must match primary (x==3 kept)")

    def test_soft_independent_set_all_honored(self):
        """Non-conflicting softs at different priorities are ALL kept (relaxation
        only drops on conflict). Guards against an over-eager drop."""
        @vsc.randobj
        class It(object):
            def __init__(s):
                s.x = vsc.rand_uint8_t()
                s.y = vsc.rand_uint8_t()
                s.z = vsc.rand_uint8_t()
            @vsc.constraint
            def c(s):
                vsc.soft(s.x == 11)
                vsc.soft(s.y == 22)
                vsc.soft(s.z == 33)

        it = It()
        for _ in range(20):
            it.randomize()
            self.assertEqual((int(it.x), int(it.y), int(it.z)), (11, 22, 33),
                             "independent softs must all be honored")


if __name__ == "__main__":
    unittest.main()
