"""A non-rand array index changed between randomize() calls. Runs on
whichever solver the suite selects.

Array expansion resolves `arr[k]` with a non-rand k to the element k names,
so k reached no randset, and the cached plan, which tracks only the non-rand
fields some randset holds, kept the first call's element: on dv-solve
`arr[2] == 9` held on every later call whatever k was.
"""
import vsc
from vsc_test_case import VscTestCase


class TestNonRandIndexChange(VscTestCase):

    def test_scalar_array_index(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 4)
                s.k = vsc.uint8_t(0)

            @vsc.constraint
            def c(s):
                s.arr[s.k] == 9
                s.arr[s.k] != s.arr[(s.k + 1) % 4]

        obj = C()
        for k in (2, 0, 3, 1):
            obj.k = k
            for _ in range(5):
                obj.randomize()
                self.assertEqual(obj.arr[k], 9, "k=%d arr=%s" % (
                    k, list(obj.arr)))

    def test_index_inside_foreach(self):
        @vsc.randobj
        class C(object):
            def __init__(s):
                s.arr = vsc.rand_list_t(vsc.uint8_t(), 4)
                s.k = vsc.uint8_t(0)

            @vsc.constraint
            def c(s):
                with vsc.foreach(s.arr, idx=True) as i:
                    with vsc.if_then(i == s.k):
                        s.arr[i] == 9
                    with vsc.else_then:
                        s.arr[i] < 9

        obj = C()
        for k in (2, 0, 3):
            obj.k = k
            for _ in range(5):
                obj.randomize()
                self.assertEqual(obj.arr[k], 9)
