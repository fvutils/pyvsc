'''
Dataclass-front-end adaptation of t_constraint_foreach.v.

`foreach` constraints whose body references the loop *index* (not just the
element): ``foreach(q[i]) x > i`` bounds a scalar by every index of a sized array,
and a second foreach reusing the same index name composes with it. Also covers a
foreach nested inside an ``if`` (the gated form) and a foreach over an empty array
(vacuously true).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintForeach(DcTestCase):

    def test_index_bound(self):
        # C: x < 7 and (foreach i) x > i over a size-5 array => x in {5,6}.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            q: list[vdc.u8] = vdc.rand(size=5)   # iterated for its indices 0..4
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def fore(self):
                self.x < 7
                with vdc.foreach(self.q, it=False, idx=True) as i:
                    self.x > i
                # Loop again with the same index name (redundant but legal).
                with vdc.foreach(self.q, it=False, idx=True) as i:
                    self.x > i

        c = my_c()
        for _ in range(50):
            c.randomize()
            self.assertIn(int(c.x), (5, 6))

    def test_gated_foreach_and_empty(self):
        # D: foreach gated by a rand predicate, plus a foreach over an empty array
        # (no constraints emitted). When posit is forced true, x in {5,6}.
        @vdc.dataclass
        class my_c(vdc.RandClass):
            posit: vdc.u1 = vdc.rand()
            q: list[vdc.u8] = vdc.rand(size=5)
            empty: list[vdc.u8] = vdc.rand(size=0)
            x: vdc.u8 = vdc.rand()

            @vdc.constraint
            def fore(self):
                self.posit == 1
                with vdc.if_then(self.posit == 1):
                    with vdc.foreach(self.empty, it=False, idx=True) as i:
                        self.x > i        # empty: contributes nothing
                    self.x < 7
                    with vdc.foreach(self.q, it=False, idx=True) as i:
                        self.x > i

        c = my_c()
        for _ in range(50):
            c.randomize()
            self.assertEqual(int(c.posit), 1)
            self.assertIn(int(c.x), (5, 6))


class TestLoopNameShadowsField(DcTestCase):
    """A loop name equal to a field name must not hide the field: in
    ``for e in self.arr: e != self.e`` the two are different (B19). Both used
    to be ``IRField(("e",))``, so the field read the element: ``e != e``."""

    def test_loop_name_equal_to_field_name(self):

        @vdc.dataclass
        class T(vdc.RandClass):
            e: vdc.u8 = vdc.rand()
            arr: list[vdc.u8] = vdc.rand(size=3)

            @vdc.constraint
            def c(self):
                self.e < 10
                for e in self.arr:
                    e != self.e
                    e < 10
                with vdc.foreach(self.arr, idx=True) as e:
                    self.arr[e] != self.e + 1
                any(e == self.e + 2 for e in self.arr)

        t = T()
        for _ in range(20):
            t.randomize()
            self.assertNotIn(t.e, t.arr)
            self.assertNotIn(t.e + 1, t.arr)
            self.assertIn(t.e + 2, t.arr)
