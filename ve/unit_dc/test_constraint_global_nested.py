'''
Dataclass-front-end adaptation of t_constraint_global_nested.v.

Hierarchical ("global") constraints that reach across nesting levels: each level
constrains a field of a deeper sub-object. Inner pins its own value to [1:10]; Mid
relates its field to the Inner field one level down (``m_x > m_inner.m_val``); Top
relates its field to the Inner field *two* levels down
(``m_y < m_mid.m_inner.m_val``). All three must hold simultaneously.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


@vdc.dataclass
class Inner(vdc.RandClass):
    m_val: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c_inner(self):
        self.m_val.inside(vdc.rangelist(vdc.rng(1, 10)))


@vdc.dataclass
class Mid(vdc.RandClass):
    m_inner: Inner = vdc.rand()
    m_x: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c_mid_global(self):
        self.m_x > self.m_inner.m_val


@vdc.dataclass
class Top(vdc.RandClass):
    m_mid: Mid = vdc.rand()
    m_y: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c_top_global(self):
        self.m_y < self.m_mid.m_inner.m_val


class TestConstraintGlobalNested(DcTestCase):

    def test_three_level_hierarchical(self):
        t = Top()
        for _ in range(50):
            t.randomize()
            inner = int(t.m_mid.m_inner.m_val)
            self.assertTrue(1 <= inner <= 10)              # c_inner
            self.assertGreater(int(t.m_mid.m_x), inner)    # c_mid_global (1 level)
            self.assertLess(int(t.m_y), inner)             # c_top_global (2 levels)
