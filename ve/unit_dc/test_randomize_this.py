'''
Dataclass-front-end adaptation of the "randomize this / nested sub-object" corpus:
t_randomize_this, t_randomize_this_with, t_randomize_this_inline,
t_randomize_complex, t_randomize_complex_arrays.

Capabilities pinned:
  - ``randomize()`` on an object randomizes its own rand fields AND recurses into
    nested rand-object fields (t_randomize_this);
  - a non-rand field keeps its value across ``randomize_with`` while a rand field
    is solved (t_randomize_this_with);
  - inline ``randomize_with`` constraints reference the target's members through
    the ``as`` proxy — SV's ``this.value`` is the dc ``it.value`` (t_randomize_this_inline).
    In dc there is no ``this`` keyword; ``it`` binds to the object being randomized,
    so the "this binds to the randomized object, not the caller" case is intrinsic;
  - a *deeply nested* sub-object reached through a chain of container fields is
    itself a RandClass instance and can be randomized directly, independent of its
    parents (t_randomize_complex), including when it is an array element
    (t_randomize_complex_arrays).
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


# --- t_randomize_this: recursive randomize of nested rand objects -----------
@vdc.dataclass
class Member(vdc.RandClass):
    m_val: vdc.u32 = vdc.rand()


@vdc.dataclass
class ClsThis(vdc.RandClass):
    m_val: vdc.u32 = vdc.rand()
    m_member: Member = vdc.rand()


# --- t_randomize_this_with: non-rand field preserved ------------------------
@vdc.dataclass
class ClsWith(vdc.RandClass):
    v_rand: vdc.u32 = vdc.rand()
    v_norand: vdc.u32 = 0            # non-rand state


# --- t_randomize_this_inline: this.member == it.member ----------------------
@vdc.dataclass
class DataItem(vdc.RandClass):
    value: vdc.u8 = vdc.rand()
    limit: vdc.u8 = vdc.rand()

    @vdc.constraint
    def default_con(self):
        self.limit in vdc.rangelist((50, 200))


# --- t_randomize_complex: deep nesting through non-rand containers ----------
@vdc.dataclass
class SubClass(vdc.RandClass):
    field: vdc.u3 = vdc.rand()


@vdc.dataclass
class MyClass(vdc.RandClass):
    sc_inst2: SubClass = vdc.rand()


@vdc.dataclass
class Deep(vdc.RandClass):
    sc_inst1: MyClass = vdc.rand()


@vdc.dataclass
class WeNeedToGoDeeper(vdc.RandClass):
    sc_inst: Deep = vdc.rand()


# --- t_randomize_complex_arrays: sub-object is an array element -------------
@vdc.dataclass
class MyClassArr(vdc.RandClass):
    sc_inst2: list[SubClass] = vdc.rand(size=2)


class TestRandomizeThis(DcTestCase):

    def test_recursive_randomize_nested(self):
        # randomize() changes both the own field and the nested object's field.
        c = ClsThis()
        c.m_val = 256
        c.m_member.m_val = 65535
        moved_own, moved_nested = False, False
        for _ in range(20):
            c.randomize()
            if int(c.m_val) != 256:
                moved_own = True
            if int(c.m_member.m_val) != 65535:
                moved_nested = True
        self.assertTrue(moved_own, "own field never re-randomized")
        self.assertTrue(moved_nested, "nested object field never re-randomized")

    def test_norand_preserved(self):
        c = ClsWith()
        c.v_norand = 42
        with c.randomize_with() as it:
            it.v_rand == 0
        self.assertEqual(int(c.v_rand), 0)
        self.assertEqual(int(c.v_norand), 42)

    def test_inline_this_member(self):
        # Test 1-3 of t_randomize_this_inline collapsed: several range windows,
        # plus a mix with the type's own default_con on `limit`.
        item = DataItem()
        for _ in range(10):
            with item.randomize_with() as it:
                it.value > 10
                it.value < 50
            self.assertTrue(11 <= int(item.value) <= 49)
            self.assertTrue(50 <= int(item.limit) <= 200)

        for _ in range(10):
            with item.randomize_with() as it:
                it.value > 20
                it.value < 30
            self.assertTrue(21 <= int(item.value) <= 29)

        for _ in range(10):
            with item.randomize_with() as it:
                it.value > 5
                it.value < 100
                it.limit > 150
            self.assertTrue(6 <= int(item.value) <= 99)
            self.assertTrue(151 <= int(item.limit) <= 200)

    def test_inline_binds_to_target(self):
        # SV Test 4: `this` binds to the randomized object even when the call is
        # issued from a different object's method. In dc `it` is always the target.
        item = DataItem()

        @vdc.dataclass
        class Caller(vdc.RandClass):
            own_value: vdc.u8 = vdc.rand()

            def do_rand(self, target):
                with target.randomize_with() as it:
                    it.value > 30
                    it.value < 40

        caller = Caller()
        for _ in range(10):
            caller.do_rand(item)
            self.assertTrue(31 <= int(item.value) <= 39)

    def test_direct_nested_subobject(self):
        # Reach a leaf through sc_inst.sc_inst1.sc_inst2 and randomize it directly.
        top = WeNeedToGoDeeper()
        seen = set()
        for _ in range(20):
            with top.sc_inst.sc_inst1.sc_inst2.randomize_with() as it:
                it.field in vdc.rangelist(1, 2, 3)
            v = int(top.sc_inst.sc_inst1.sc_inst2.field)
            self.assertTrue(1 <= v <= 3)
            seen.add(v)
        self.assertGreater(len(seen), 1, "leaf field never varied")

    def test_direct_array_element_subobject(self):
        # Randomize a composite-array *element* directly (a standalone RandClass).
        m = MyClassArr()
        for _ in range(20):
            with m.sc_inst2[1].randomize_with() as it:
                it.field in vdc.rangelist(1, 2, 3)
            self.assertTrue(1 <= int(m.sc_inst2[1].field) <= 3)
