'''
Phase 3 -- the bulk array path.

Three shortcuts are under test here, and each one is a shortcut around a
*callback*, which is the dangerous kind:

  * ``FieldArrayModel`` walks its elements with an inlined loop instead of one
    method call per element, for ``pre_randomize`` / ``post_randomize`` /
    ``set_used_rand``. Guarded by ``_is_bulk()``: every element must be an
    exact-type ``FieldScalarModel`` with no ``rand_if``.
  * ``post_randomize`` is called on an element only when it actually has a
    solver var to convert.
  * array writeback reads ``field.val.v`` directly instead of
    ``get_val()`` + ``int()``.

So the tests below are mostly about the shapes that must NOT take the
shortcut (enum arrays, composite arrays, rand-sized arrays, the Boolector
path) and about the observable side effects surviving (hooks firing, exact
``int`` values, per-element independence).
'''
import unittest
from enum import IntEnum

import vsc
import vsc.dc as vdc

from dc_test_case import DcTestCase


class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2


@vdc.dataclass
class Elem(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a > 200


@vdc.dataclass
class Scalars(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=8)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


@vdc.dataclass
class Signed(vdc.RandClass):
    arr: list[vdc.s8] = vdc.rand(size=8)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it >= -40
            it <= -1


@vdc.dataclass
class Enums(vdc.RandClass):
    cols: list[Color] = vdc.rand(size=4)


@vdc.dataclass
class Composites(vdc.RandClass):
    elems: list[Elem] = vdc.rand(size=3)


@vdc.dataclass
class RandSized(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(max_size=6)

    @vdc.constraint
    def c(self):
        self.arr.size > 1
        self.arr.size < 5
        with vdc.foreach(self.arr) as it:
            it > 100


@vdc.dataclass
class Coupled(vdc.RandClass):
    """Elements coupled to each other: not T0-eligible, so the array is solved
    element-by-element and every element gets a solver var. The bulk walk must
    still fire their post_randomize (that is what converts the var)."""
    arr: list[vdc.u8] = vdc.rand(size=6)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr, it=False, idx=True) as i:
            with vdc.if_then(i > 0):
                self.arr[i] > self.arr[i - 1]


@vdc.dataclass
class Hooked(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=4)
    n_pre: int = 0
    n_post: int = 0
    seen: int = 0

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 10

    def pre_randomize(self):
        self.n_pre += 1

    def post_randomize(self):
        # Must observe the randomized array, not the previous value.
        self.n_post += 1
        self.seen = sum(self.arr)


def _model(obj):
    from vsc.dc import solve_view
    comp, fms = solve_view.get_solve_model(obj, type(obj)._vsc_type_model)
    return fms


class TestBulkEligibility(DcTestCase):
    """Which arrays take the inlined walk."""

    def test_scalar_array_is_bulk(self):
        o = Scalars()
        o.randomize()
        self.assertTrue(_model(o)["arr"]._is_bulk())

    def test_enum_array_is_not_bulk(self):
        # EnumFieldModel rebinds `val` and takes its domain from the member
        # set: the shortcut's reasoning does not hold for it.
        o = Enums()
        o.randomize()
        self.assertFalse(_model(o)["cols"]._is_bulk())

    def test_composite_array_is_not_bulk(self):
        o = Composites()
        o.randomize()
        self.assertFalse(_model(o)["elems"]._is_bulk())

    def test_classic_scalar_array_is_bulk(self):
        @vsc.randobj
        class A(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 6)

        o = A()
        o.randomize()
        self.assertTrue(o.get_model().field_l[0]._is_bulk())

    def test_bulk_flag_is_invalidated_by_mutation(self):
        from vsc.model.field_array_model import FieldArrayModel
        from vsc.model.field_composite_model import FieldCompositeModel
        from vsc.model.field_scalar_model import FieldScalarModel

        arr = FieldArrayModel("a", FieldScalarModel("t", 8, False, True),
                              True, None, 8, False, True, False)
        arr.add_field()
        self.assertTrue(arr._is_bulk())
        # A composite element must flip it back.
        arr.append(FieldCompositeModel("c", True))
        self.assertFalse(arr._is_bulk())
        arr.pop(1)
        self.assertTrue(arr._is_bulk())
        arr.clear()
        self.assertTrue(arr._is_bulk())


class TestBulkCorrectness(DcTestCase):
    """Values, types and lengths, for every array kind."""

    def test_scalar_values(self):
        o = Scalars()
        for _ in range(200):
            o.randomize()
            self.assertEqual(len(o.arr), 8)
            self.assertTrue(all(3 <= v <= 249 for v in o.arr), o.arr)

    def test_writeback_produces_exact_ints(self):
        # The fast writeback drops the `int()` per element, so it relies on
        # `val.v` always being an exact int. A bool or an int *subclass*
        # leaking through would be invisible to a range check.
        o = Scalars()
        o.randomize()
        for v in o.arr:
            self.assertIs(type(v), int)

    def test_elements_are_independent(self):
        # One value reused across the array would satisfy every range check.
        o = Scalars()
        same = 0
        for _ in range(200):
            o.randomize()
            if len(set(o.arr)) == 1:
                same += 1
        self.assertEqual(same, 0)

    def test_signed_elements(self):
        o = Signed()
        for _ in range(100):
            o.randomize()
            self.assertTrue(all(-40 <= v <= -1 for v in o.arr), o.arr)
            self.assertTrue(all(type(v) is int for v in o.arr))

    def test_enum_array_writes_back_members(self):
        o = Enums()
        for _ in range(50):
            o.randomize()
            self.assertEqual(len(o.cols), 4)
            self.assertTrue(all(isinstance(c, Color) for c in o.cols), o.cols)

    def test_composite_array_elements_are_randomized(self):
        o = Composites()
        for _ in range(50):
            o.randomize()
            self.assertEqual(len(o.elems), 3)
            for e in o.elems:
                self.assertGreater(e.a, 200)

    def test_rand_sized_array_exposes_solved_length(self):
        o = RandSized()
        lens = set()
        for _ in range(100):
            o.randomize()
            lens.add(len(o.arr))
            self.assertTrue(1 < len(o.arr) < 5)
            self.assertTrue(all(v > 100 for v in o.arr), o.arr)
        self.assertGreater(len(lens), 1, "size did not vary")

    def test_coupled_elements_still_solve(self):
        # Not T0-eligible: every element gets a solver var, so this is the path
        # where the bulk post_randomize must actually call through.
        o = Coupled()
        for _ in range(50):
            o.randomize()
            self.assertEqual(len(o.arr), 6)
            for i in range(1, 6):
                self.assertGreater(o.arr[i], o.arr[i - 1], o.arr)


class TestBulkHooks(DcTestCase):
    """The shortcuts skip callbacks only where they are provably no-ops."""

    def test_object_hooks_still_fire_and_see_values(self):
        o = Hooked()
        for i in range(1, 11):
            o.randomize()
            self.assertEqual(o.n_pre, i)
            self.assertEqual(o.n_post, i)
            self.assertEqual(o.seen, sum(o.arr))
            self.assertTrue(all(v > 10 for v in o.arr))

    def test_composite_element_hooks_still_fire(self):
        @vdc.dataclass
        class E(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            hits: int = 0

            def post_randomize(self):
                self.hits += 1

        @vdc.dataclass
        class Holder(vdc.RandClass):
            es: list[E] = vdc.rand(size=3)

        o = Holder()
        for i in range(1, 6):
            o.randomize()
            for e in o.es:
                self.assertEqual(e.hits, i)

    def test_rand_mode_off_freezes_the_array(self):
        # set_used_rand's inlined form must honor per-element rand_mode.
        o = Scalars()
        o.randomize()
        frozen = list(o.arr)
        o.set_rand_mode("arr", False)
        try:
            for _ in range(20):
                o.randomize()
                self.assertEqual(list(o.arr), frozen)
        finally:
            o.set_rand_mode("arr", True)
        moved = False
        for _ in range(20):
            o.randomize()
            if list(o.arr) != frozen:
                moved = True
        self.assertTrue(moved, "array stayed frozen after rand_mode was restored")


class TestBulkBackends(DcTestCase):
    """On Boolector every element gets a solver var, so the bulk walk takes its
    other branch -- the one that must call through."""

    def _backends(self):
        cur = vsc.get_solver_backend()
        out = []
        for name in ("dv-solve", "boolector"):
            try:
                vsc.set_solver_backend(name)
                out.append(name)
            except Exception:
                pass
        vsc.set_solver_backend(cur)
        return out

    def test_all_backends_agree_on_support(self):
        import vsc.model.randomizer as rnd
        cur = vsc.get_solver_backend()
        saved_t0 = rnd._T0_ENABLED
        try:
            for name in self._backends():
                for t0 in (True, False):
                    vsc.set_solver_backend(name)
                    rnd._T0_ENABLED = t0
                    with self.subTest(backend=name, t0=t0):
                        o = Scalars()
                        for _ in range(50):
                            o.randomize()
                            self.assertEqual(len(o.arr), 8)
                            self.assertTrue(
                                all(3 <= v <= 249 for v in o.arr), o.arr)
                            self.assertTrue(
                                all(type(v) is int for v in o.arr))
        finally:
            rnd._T0_ENABLED = saved_t0
            vsc.set_solver_backend(cur)


if __name__ == "__main__":
    unittest.main()
