"""if/else soundness — the constraint must actually hold in the model (KF-1).

`doc/notes/known_failures.md` KF-1: dv-solve returned models that VIOLATE an
if/else constraint 63% of the time, silently. The whole class was invisible
because the existing tests only assert that `randomize()` *succeeds* — never that
the result satisfies the constraint.

Root cause: when the two sides of a comparison have different declared widths,
the narrower one arrives wrapped in a zero-extend (`c == zero_extend(d)`). The
native OR-leaf classifier did not see through that wrapper, so the leaf was
rejected, the whole disjunction failed to flatten, and compilation fell back to a
Boolean-guard encoding whose primary propagation is unsound. Only the *else*
comparison was width-mismatched here, which is why only the else branch broke.

So these tests keep two things honest, and the mismatched widths are load-bearing
in both:

1. every draw satisfies the branch its guard selected, and
2. both branches are actually exercised (a solver that only ever took the *then*
   branch would pass an assertion-only check while proving nothing).
"""
import vsc

from vsc_test_case import VscTestCase


class TestDvSolveIfElseSoundness(VscTestCase):

    N = 400

    def _draw(self, obj):
        """N randomizations; returns the list of (a, b, c, d) tuples."""
        out = []
        for _ in range(self.N):
            obj.randomize()
            out.append((int(obj.a), int(obj.b), int(obj.c), int(obj.d)))
        return out

    def test_if_else_mixed_width_holds(self):
        """The KF-1 shape verbatim: 2-bit vs 1-bit in the else comparison."""
        @vsc.randobj
        class S(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(2)
                self.d = vsc.rand_bit_t(1)

            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.c < self.d
                with vsc.else_then():
                    self.c == self.d

        draws = self._draw(S())
        for a, b, c, d in draws:
            if a < b:
                self.assertLess(c, d, "then-branch violated: %s" % ((a, b, c, d),))
            else:
                self.assertEqual(c, d, "else-branch violated: %s" % ((a, b, c, d),))
        # The else branch must actually be reached -- `c < d` over a 2-bit c and
        # 1-bit d has exactly one solution, so the then branch is the rare one and
        # the else branch is where the bug lived.
        self.assertTrue(any(a >= b for a, b, _, _ in draws),
                        "else branch never exercised")

    def test_if_else_unsat_then_branch(self):
        """The worst KF-1 variant: the then-branch is UNSAT (`c > 3` over 2-bit c),
        so `a < b` must never hold and `c == d` must always hold. This had the
        highest violation rate (425/600) -- the more constrained the then-branch,
        the less the else-branch was enforced."""
        @vsc.randobj
        class S(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(2)
                self.d = vsc.rand_bit_t(1)

            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.c > 3
                with vsc.else_then():
                    self.c == self.d

        for a, b, c, d in self._draw(S()):
            self.assertGreaterEqual(a, b, "guard true with an UNSAT then-branch")
            self.assertEqual(c, d, "else-branch violated: %s" % ((a, b, c, d),))

    def test_if_else_same_width_holds(self):
        """The control: same-width operands never hit the extend wrapper. Guards
        against a fix that only papers over the mismatched case."""
        @vsc.randobj
        class S(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(4)
                self.d = vsc.rand_bit_t(4)

            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.c < self.d
                with vsc.else_then():
                    self.c == self.d

        draws = self._draw(S())
        for a, b, c, d in draws:
            if a < b:
                self.assertLess(c, d, "then-branch violated: %s" % ((a, b, c, d),))
            else:
                self.assertEqual(c, d, "else-branch violated: %s" % ((a, b, c, d),))
        self.assertTrue(any(a < b for a, b, _, _ in draws), "then never exercised")
        self.assertTrue(any(a >= b for a, b, _, _ in draws), "else never exercised")

    def test_mixed_width_disjunction_holds(self):
        """A plain mixed-width disjunction, no if/else.

        This one passes *both* before and after the fix -- measured. A standalone
        OR that loses a leaf still gets enough from the remaining propagation to
        stay sound; it takes the if/else pair of linked disjunctions to go wrong.
        Kept as a guard on the neighbouring shape, not as a reproduction."""
        @vsc.randobj
        class S(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.rand_bit_t(3)
                self.d = vsc.rand_bit_t(1)

            @vsc.constraint
            def c_c(self):
                (self.c == self.d) | (self.c == 5)
                self.a == self.b

        for a, b, c, d in self._draw(S()):
            self.assertTrue(c == d or c == 5,
                            "disjunction violated: c=%d d=%d" % (c, d))
