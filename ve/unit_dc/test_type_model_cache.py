'''
Correctness of the per-TYPE solve-model cache (solve_view shares one model object
across all instances of a type, rebinding values/writeback-target per call).

Pins the cases most at risk from sharing: multiple coexisting instances, diverging
non-rand values referenced in constraints (plan-cache invalidation), and that
writeback lands on the right instance.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestTypeModelCache(DcTestCase):

    def test_coexisting_instances_independent(self):

        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a < self.b

        x = C()
        y = C()
        for _ in range(20):
            x.randomize()
            y.randomize()
            # Each instance independently satisfies the constraint and holds its
            # own solved values (writeback targeted the right object).
            self.assertLess(x.a, x.b)
            self.assertLess(y.a, y.b)

    def test_diverging_nonrand_values(self):
        # A non-rand field referenced in a constraint differs per instance; the
        # shared model's plan must re-derive per instance (no stale carry-over).

        @vdc.dataclass
        class C(vdc.RandClass):
            n: vdc.u8 = vdc.field(default=0)
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.a == self.n

        objs = [C() for _ in range(4)]
        for i, o in enumerate(objs):
            o.n = i * 3
        # Interleave randomize across instances with different bound values.
        for _ in range(5):
            for i, o in enumerate(objs):
                o.randomize()
                self.assertEqual(o.a, i * 3)

    def test_shared_model_object(self):
        # Sanity: two instances really do share the cached model object (that is
        # what makes the plan/translation caches hit across instances).

        @vdc.dataclass
        class C(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

        x = C()
        y = C()
        x.randomize()
        y.randomize()
        node_x = type(x).__dict__.get("_vsc_solve_model")
        self.assertIsNotNone(node_x)
        self.assertIs(node_x, type(y).__dict__.get("_vsc_solve_model"))
