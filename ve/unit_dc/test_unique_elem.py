'''
Dataclass-front-end adaptation of t_randomize_unique_elem.v (IEEE 18.5.9):
``unique`` over an *explicit subset* of array elements, not the whole array.

  - ``unique {arr[2..6]}`` of a size-10 ``list[u4]`` — only those 5 elements
    must be pairwise distinct; the other 5 are free (and, in a 16-value domain,
    may legally collide with the constrained set or each other);
  - ``unique {data[1..4]}`` of a size-8 array — 4 distinct elements;
  - ``unique {val[0]}`` — a single-element unique set is vacuously satisfiable.

Constant array subscripts resolve to concrete elements at build time, so these
run on both back-ends (no symbolic index). u4 (bit[3:0]) keeps the value space
small so a collision would be near-certain if uniqueness were not enforced.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class UniqueElemSubset(vdc.RandClass):
    arr: list[vdc.u4] = vdc.rand(size=10)

    @vdc.constraint
    def unique_subset(self):
        vdc.unique(self.arr[2], self.arr[3], self.arr[4],
                   self.arr[5], self.arr[6])


@vdc.dataclass
class UniqueElemFour(vdc.RandClass):
    data: list[vdc.u4] = vdc.rand(size=8)

    @vdc.constraint
    def unique_data(self):
        vdc.unique(self.data[1], self.data[2], self.data[3], self.data[4])


@vdc.dataclass
class UniqueElemSingle(vdc.RandClass):
    val: list[vdc.u4] = vdc.rand(size=4)

    @vdc.constraint
    def unique_single(self):
        vdc.unique(self.val[0])


class TestUniqueElem(DcTestCase):

    def test_subset_unique(self):
        # arr[2..6] pairwise distinct; every draw, and the set varies.
        ues = UniqueElemSubset()
        seen = set()
        for _ in range(20):
            ues.randomize()
            sub = [int(ues.arr[i]) for i in range(2, 7)]
            self.assertEqual(len(set(sub)), 5, "arr[2..6] not unique: %s" % sub)
            seen.add(tuple(sub))
        self.assertGreater(len(seen), 1, "unique subset never varied")

    def test_four_unique(self):
        uef = UniqueElemFour()
        for _ in range(20):
            uef.randomize()
            sub = [int(uef.data[i]) for i in range(1, 5)]
            self.assertEqual(len(set(sub)), 4, "data[1..4] not unique: %s" % sub)

    def test_single_unique_trivial(self):
        # A one-element unique set is always satisfiable and unconstrains val[0].
        uesgl = UniqueElemSingle()
        seen = set()
        for _ in range(20):
            uesgl.randomize()
            seen.add(int(uesgl.val[0]))
        self.assertGreater(len(seen), 1, "single unique element never varied")

    def test_unconstrained_elems_are_free(self):
        # Elements outside the unique set (arr[0], arr[1], arr[7..9]) are not
        # forced distinct — over many draws at least one collision with the
        # constrained set is expected, confirming the constraint is a subset.
        ues = UniqueElemSubset()
        saw_free_collision = False
        for _ in range(40):
            ues.randomize()
            constrained = {int(ues.arr[i]) for i in range(2, 7)}
            free = [int(ues.arr[i]) for i in (0, 1, 7, 8, 9)]
            if any(f in constrained for f in free):
                saw_free_collision = True
                break
        self.assertTrue(
            saw_free_collision,
            "free elements never collided with the unique set — subset "
            "semantics may be over-constraining")
