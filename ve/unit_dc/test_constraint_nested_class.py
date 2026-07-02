'''
Dataclass-front-end adaptation of t_constraint_nested_class.v.

A nested (composite) rand object whose own constraint pins a scalar to a constant
and ties every element of a fixed array together with a foreach equality chain
(``array[i] == array[i-1]``), randomized through the enclosing object.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc

LEN = 4


@vdc.dataclass
class A(vdc.RandClass):
    x: vdc.u8 = vdc.rand()
    array: list[vdc.u8] = vdc.rand(size=5)

    @vdc.constraint
    def a_c(self):
        self.x <= LEN
        self.x >= LEN                       # => x == LEN
        with vdc.foreach(self.array, it=False, idx=True) as i:
            with vdc.if_then(i > 0):
                self.array[i] == self.array[i - 1]   # all elements equal


@vdc.dataclass
class B(vdc.RandClass):
    a: A = vdc.rand()


class TestConstraintNestedClass(DcTestCase):

    def test_nested_array_chain(self):
        b = B()
        for _ in range(20):
            b.randomize()
            self.assertEqual(int(b.a.x), LEN)
            vals = [int(v) for v in b.a.array]
            # The equality chain forces every element to the same value.
            self.assertEqual(len(set(vals)), 1, vals)
