'''
Dataclass-front-end parallel of ve/unit/test_scalar_array.py.

Fixed-size (test_smoke, test_large_arrays) and random-size (test_randsize_1/2)
scalar arrays. A random-size array is a ``list[T]`` field with no ``size=`` — its
length is the (constrained) ``arr.size``. Note the dc translation reads list length
with ``len(it.my_l)`` (a plain Python list), where the classic uses ``it.my_l.size``.
The compound/enum array cases land with the composite / enum-array follow-ons.
'''
import time

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestScalarArray(DcTestCase):

    def test_smoke(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            my_l: list[vdc.u8] = vdc.rand(size=10)

            @vdc.constraint
            def my_l_c(self):
                with vdc.foreach(self.my_l) as it:
                    it < 10

        it = my_item_c()

        hist = []
        for i in range(10):
            hist.append([0] * 10)

        for i in range(100):
            it.randomize()

            for i, e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

    def test_large_arrays(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            my_l_1: list[vdc.u8] = vdc.rand(size=1000)
            my_l_2: list[vdc.u8] = vdc.rand(size=1000)

            @vdc.constraint
            def my_l_c(self):
                with vdc.foreach(self.my_l_1) as it:
                    it < 10
                with vdc.foreach(self.my_l_2) as it:
                    it < 10

        it = my_item_c()

        count = 4
        for i in range(count):
            it.randomize()

            for i, e in enumerate(it.my_l_1):
                self.assertLess(e, 10)
            for i, e in enumerate(it.my_l_2):
                self.assertLess(e, 10)

    def test_randsize_1(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            my_l: list[vdc.u8] = vdc.rand()   # random size

            @vdc.constraint
            def my_l_c(self):
                self.my_l.size == 10
                with vdc.foreach(self.my_l) as it:
                    it < 10

        it = my_item_c()
        for i in range(100):
            it.randomize()
            self.assertEqual(len(it.my_l), 10)
            for i, e in enumerate(it.my_l):
                self.assertLess(e, 10)

    def test_randsize_2(self):

        @vdc.dataclass
        class my_item_c(vdc.RandClass):
            my_l: list[vdc.u8] = vdc.rand()   # random size

            @vdc.constraint
            def my_l_c(self):
                self.my_l.size > 0
                self.my_l.size <= 4
                with vdc.foreach(self.my_l) as it:
                    it < 10

        it = my_item_c()
        size_hist = [0] * 4
        for i in range(100):
            it.randomize()
            self.assertLessEqual(len(it.my_l), 4)
            self.assertGreater(len(it.my_l), 0)
            size_hist[len(it.my_l) - 1] += 1
            for i, e in enumerate(it.my_l):
                self.assertLess(e, 10)
