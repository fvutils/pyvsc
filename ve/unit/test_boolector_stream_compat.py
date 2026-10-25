'''
Boolector keeps the 0.9.x value stream (pyvsc 1.x promise).

Boolector is the 1.x default, and a given seed must keep producing the values
0.9.x produced. Two 1.x additions would change them, so both are off on
Boolector: the T0 direct-draw tier, and the faster ``(n-1).bit_length()`` width
of the unconstrained draw. These tests pin both defaults, and check that an
unconstrained draw on Boolector consumes the random stream exactly as
``random.randint`` (what 0.9.x called) does.
'''
import random
from enum import IntEnum

import vsc
import vsc.model.randomizer as rnd
from types import SimpleNamespace

from vsc_test_case import VscTestCase, requires_boolector


@vsc.randobj
class _Free(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(8)    # n = 256: the widths differ (9 vs 8 bits)
        self.b = vsc.rand_bit_t(1)
        self.c = vsc.rand_bit_t(13)
        self.d = vsc.rand_uint32_t()


class _E(IntEnum):
    A = 1
    B = 2


@vsc.randobj
class _Mixed(object):
    # The shape of v0.9.6's test_attr_enum::test_rand_int_enum: the enum takes
    # the general draw loop and the scalar the fast lane.
    def __init__(self):
        self.a = vsc.rand_enum_t(_E)
        self.b = vsc.enum_t(_E)
        self.c = vsc.rand_uint8_t()


# The defaults depend only on the back-end's name, so a stand-in object lets
# these run on CI legs where one of the solvers isn't installed.
_BTOR = SimpleNamespace(name="boolector")
_DVS = SimpleNamespace(name="dv-solve")


class TestBoolectorStreamCompat(VscTestCase):

    def test_t0_default_follows_backend(self):
        saved = rnd._T0_SETTING
        try:
            rnd._T0_SETTING = None
            self.assertFalse(rnd._t0_enabled(_BTOR))
            self.assertTrue(rnd._t0_enabled(_DVS))
            rnd._T0_SETTING = True        # VSC_T0=1 opts every back-end in
            self.assertTrue(rnd._t0_enabled(_BTOR))
            rnd._T0_SETTING = False       # VSC_T0=0 turns it off everywhere
            self.assertFalse(rnd._t0_enabled(_DVS))
        finally:
            rnd._T0_SETTING = saved

    def test_draw_width_follows_backend(self):
        self.assertTrue(rnd._randint_compat(_BTOR))
        self.assertFalse(rnd._randint_compat(_DVS))

    @requires_boolector
    def test_unconstrained_draw_matches_randint(self):
        from vsc.impl import ctor
        saved = ctor._solver_override
        vsc.set_solver_backend("boolector")
        try:
            o = _Free()
            o.set_randstate(vsc.RandState.mkFromSeed(7))
            got = []
            for _ in range(20):
                o.randomize()
                got.append((o.a, o.b, o.c, o.d))
        finally:
            vsc.set_solver_backend(saved)

        rng = vsc.RandState.mkFromSeed(7).rng
        exp = [(rng.randint(0, 255), rng.randint(0, 1),
                rng.randint(0, 8191), rng.randint(0, 0xFFFFFFFF))
               for _ in range(20)]
        self.assertEqual(got, exp)

    @requires_boolector
    def test_mixed_kinds_keep_draw_order(self):
        # 0.9.x drew a first, then c. The fast lane must not move c ahead.
        from vsc.impl import ctor
        saved = ctor._solver_override
        vsc.set_solver_backend("boolector")
        try:
            o = _Mixed()
            o.set_randstate(vsc.RandState.mkFromSeed(11))
            got = []
            for _ in range(20):
                o.randomize()
                got.append((int(o.a), o.c))
        finally:
            vsc.set_solver_backend(saved)

        rng = vsc.RandState.mkFromSeed(11).rng
        exp = [(rng.randint(1, 2), rng.randint(0, 255)) for _ in range(20)]
        self.assertEqual(got, exp)
