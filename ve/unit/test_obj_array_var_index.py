"""A reference through an object array with a random index: `objs[i].v`,
`objs[i].sub.w`, `objs[i].arr[j]` (v2 plan V10). Runs on whichever solver
the suite selects.

Every consumer resolved such a reference from the index's value before the
solve: the randset held only that one element, Boolector built only it, and
the bound visitor bounded it, so `objs[0].v == 3` held on every draw while i
moved. dv-solve deferred. It fails on Boolector from the second call.
"""
import vsc
from vsc_test_case import VscTestCase


@vsc.randobj
class Sub(object):
    def __init__(s):
        s.w = vsc.rand_uint8_t()


@vsc.randobj
class Elem(object):
    def __init__(s):
        s.v = vsc.rand_uint8_t()
        s.sub = vsc.rand_attr(Sub())
        s.arr = vsc.rand_list_t(vsc.uint8_t(), 3)


def _objs_class(body):
    @vsc.randobj
    class C(object):
        def __init__(s):
            s.objs = vsc.rand_list_t(Elem(), 0)
            for _ in range(4):
                s.objs.append(Elem())
            s.i = vsc.rand_uint8_t()
            s.j = vsc.rand_uint8_t()

        @vsc.constraint
        def c(s):
            s.i < 4
            s.j < 3
            body(s)
    return C


class TestObjArrayVarIndex(VscTestCase):

    def _draws(self, C, check, n=200):
        obj = C()
        i_seen = set()
        j_seen = set()
        for _ in range(n):
            obj.randomize()
            self.assertTrue(check(obj), "constraint violated: i=%d j=%d" % (
                obj.i, obj.j))
            i_seen.add(int(obj.i))
            j_seen.add(int(obj.j))
        return obj, i_seen, j_seen

    def test_field(self):
        C = _objs_class(lambda s: s.objs[s.i].v == 3)
        _, i_seen, _ = self._draws(C, lambda c: c.objs[c.i].v == 3)
        self.assertEqual(i_seen, {0, 1, 2, 3})

    def test_other_elements_are_not_pinned(self):
        """The bound visitor took `objs[i].v == 3` as a bound on the element
        the index's old value named, so that element was always 3."""
        C = _objs_class(lambda s: s.objs[s.i].v == 3)
        obj = C()
        others = set()
        for _ in range(100):
            obj.randomize()
            for k in range(4):
                if k != obj.i:
                    others.add(int(obj.objs[k].v))
        self.assertGreater(len(others), 10)

    def test_nested_object_field(self):
        C = _objs_class(lambda s: s.objs[s.i].sub.w == 4)
        _, i_seen, _ = self._draws(C, lambda c: c.objs[c.i].sub.w == 4)
        self.assertEqual(i_seen, {0, 1, 2, 3})

    def test_fixed_index_into_a_member_array(self):
        C = _objs_class(lambda s: s.objs[s.i].arr[1] == 5)
        _, i_seen, _ = self._draws(C, lambda c: c.objs[c.i].arr[1] == 5)
        self.assertEqual(i_seen, {0, 1, 2, 3})

    def test_random_index_into_a_member_array(self):
        C = _objs_class(lambda s: s.objs[s.i].arr[s.j] == 6)
        _, i_seen, j_seen = self._draws(
            C, lambda c: c.objs[c.i].arr[c.j] == 6)
        self.assertEqual(i_seen, {0, 1, 2, 3})
        self.assertEqual(j_seen, {0, 1, 2})

    def test_fixed_object_random_member_index(self):
        """`objs[2].arr[j]`: the subscript's array is reached through an
        object. It raised NotImplementedError on both solvers."""
        C = _objs_class(lambda s: s.objs[2].arr[s.j] == 7)
        _, _, j_seen = self._draws(C, lambda c: c.objs[2].arr[c.j] == 7)
        self.assertEqual(j_seen, {0, 1, 2})

    def test_two_random_indexes_related(self):
        def body(s):
            s.i != s.j
            s.objs[s.i].v + s.objs[s.j].v == 100
        C = _objs_class(body)
        self._draws(C, lambda c: c.i != c.j
                    and c.objs[c.i].v + c.objs[c.j].v == 100)

    def test_relation_to_another_random_field(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.objs = vsc.rand_list_t(Elem(), 0)
                for _ in range(4):
                    s.objs.append(Elem())
                s.i = vsc.rand_uint8_t()
                s.x = vsc.rand_uint8_t()

            @vsc.constraint
            def c(s):
                s.i < 4
                s.x < 10
                s.objs[s.i].v > s.x
                s.objs[s.i].v < 12

        obj = C()
        for _ in range(100):
            obj.randomize()
            self.assertTrue(obj.x < obj.objs[obj.i].v < 12)

    def test_non_rand_index(self):
        """A non-rand index has its value: it names one element."""
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.objs = vsc.rand_list_t(Elem(), 0)
                for _ in range(4):
                    s.objs.append(Elem())
                s.k = vsc.uint8_t(0)

            @vsc.constraint
            def c(s):
                s.objs[s.k].v == 9

        obj = C()
        for k in (2, 0, 3):
            obj.k = k
            for _ in range(5):
                obj.randomize()
                self.assertEqual(obj.objs[k].v, 9)
