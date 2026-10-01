"""Pythonic range-membership syntax in vdc constraints.

vdc constraints are AST-parsed and never executed, so ``in`` / ``not in`` carry no
``__contains__``/bool-coercion hazard and lower directly to ``inside``. Four spellings
denote a value set:

  * ``[(lo, hi)]`` and ``[vdc.rng(lo, hi)]``   -- inclusive
  * ``vdc.r[lo:hi]``                           -- inclusive (SystemVerilog ``[lo:hi]``)
  * ``range(lo, hi)``                          -- HALF-OPEN (Python ``range``)
  * ``[v0, v1, ...]``                          -- a discrete set

The inclusive/half-open split is deliberate: each spelling means what its own language
already means. ``test_range_vs_slice_endpoint`` pins the difference so it cannot drift.

Regression lock for **D-3**: ``_ranges()`` used to splat the arguments of *any*
``ast.Call``, so ``a in range(3, 50)`` silently compiled to ``a inside {3, 50}`` -- two
values instead of 47, and it emitted 50, which ``range(3, 50)`` excludes. No error was
raised. ``test_range_is_half_open`` / ``test_unknown_call_rejected`` lock both halves.

Non-symbolic membership, so every case runs on **both** back-ends.
"""
import random

from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.dc.constraint_parser import ConstraintParseError


def _draw(cls, n=400):
    """Distinct values produced by `n` seeded randomizations of a one-field class."""
    obj = cls()
    out = set()
    for i in range(n):
        random.seed(i)
        obj.randomize()
        out.add(int(obj.a))
    return out


class TestRangeSyntax(DcTestCase):

    # ---- inclusive spellings: all three denote 3..50 -------------------- #

    def test_tuple_range_inclusive(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in [(3, 50)]

        self.assertEqual(_draw(C), set(range(3, 51)))

    def test_rng_inclusive(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in [vdc.rng(3, 50)]

        self.assertEqual(_draw(C), set(range(3, 51)))

    def test_slice_inclusive(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in vdc.r[3:50]

        self.assertEqual(_draw(C), set(range(3, 51)))

    # ---- half-open spelling (D-3) --------------------------------------- #

    def test_range_is_half_open(self):
        """``a in range(3, 50)`` must be 3..49 -- 47 values, never 50.

        Before the D-3 fix this produced exactly {3, 50}.
        """
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in range(3, 50)

        got = _draw(C)
        self.assertEqual(got, set(range(3, 50)))
        self.assertNotIn(50, got)
        self.assertEqual(len(got), 47)

    def test_range_single_arg(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in range(5)

        self.assertEqual(_draw(C), {0, 1, 2, 3, 4})

    def test_range_vs_slice_endpoint(self):
        """The one difference between the two range spellings, pinned."""
        @vdc.dataclass
        class Half(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in range(3, 50)

        @vdc.dataclass
        class Incl(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in vdc.r[3:50]

        half, incl = _draw(Half), _draw(Incl)
        self.assertEqual(incl - half, {50})
        self.assertEqual(half - incl, set())

    # ---- discrete sets stay discrete ------------------------------------ #

    def test_value_list_is_a_set(self):
        """``[3, 50]`` is two values, not a range -- unchanged by the D-3 fix."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in [3, 50]

        self.assertEqual(_draw(C), {3, 50})

    # ---- unions --------------------------------------------------------- #

    def test_union_of_ranges(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in [range(3, 6), range(9, 12)]

        self.assertEqual(_draw(C), {3, 4, 5, 9, 10, 11})

    def test_union_of_slices(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in vdc.r[3:5, 9:11]

        self.assertEqual(_draw(C), {3, 4, 5, 9, 10, 11})

    def test_mixed_values_and_ranges(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a in [1, 2, (100, 200)]

        # Containment only, not spread -- matching the posture in test_inside.py:
        # for a *gapped* value set the back-ends legally differ on which members
        # they favour. Measured over 2000 draws: dv-solve hits {1,2} 1.90% of the
        # time (uniform would be 1.94%) and covers all 103 values; boolector never
        # picks 1 or 2 at all (101/103 covered). Asserting spread here would encode
        # a dv-solve-only property into a both-back-end test.
        got = _draw(C)
        self.assertTrue(got <= ({1, 2} | set(range(100, 201))))
        self.assertTrue(any(100 <= v <= 200 for v in got))

    # ---- complement ------------------------------------------------------ #

    def test_not_in_range(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a not in range(0, 250)

        self.assertEqual(_draw(C), set(range(250, 256)))

    def test_not_in_slice(self):
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a not in vdc.r[0:250]

        self.assertEqual(_draw(C), set(range(251, 256)))

    # ---- non-literal endpoints still work -------------------------------- #

    def test_range_with_field_endpoint(self):
        """``range(lo, hi)`` with a field upper bound lowers to ``hi - 1``."""
        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            hi: vdc.u8 = vdc.field(default=10)

            @vdc.constraint
            def c(self):
                self.a in range(2, self.hi)

        self.assertEqual(_draw(C), set(range(2, 10)))

    # ---- the D-3 guard ---------------------------------------------------- #

    def test_unknown_call_rejected(self):
        """An unrecognized call must be a hard parse error, never an arg-splat."""
        with self.assertRaises(ConstraintParseError) as cm:
            @vdc.dataclass
            class C(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c(self):
                    self.a in sorted(3, 50)
        self.assertIn("unsupported call", str(cm.exception))

    def test_slice_with_step_rejected(self):
        with self.assertRaises(ConstraintParseError):
            @vdc.dataclass
            class C(vdc.RandClass):
                a: vdc.u8 = vdc.rand()

                @vdc.constraint
                def c(self):
                    self.a in vdc.r[3:50:2]

    # ---- the runtime object is real outside a constraint ------------------ #

    def test_r_runtime_builds_rangelist(self):
        from vsc.types import rangelist
        self.assertIsInstance(vdc.r[3:50], rangelist)
        self.assertIsInstance(vdc.r[3:5, 9:11], rangelist)
        with self.assertRaises(TypeError):
            vdc.r[3]
        with self.assertRaises(TypeError):
            vdc.r[3:50:2]
