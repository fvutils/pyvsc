"""
Base TestCase for the parallel dataclass-front-end suite (``ve/unit_dc``).

Mirrors ``ve/unit/vsc_test_case.py`` exactly (same seeded determinism and
ctor setup/teardown) so results are directly comparable to the classic suite.
"""
from unittest import TestCase
import random

from vsc.impl import ctor


class DcTestCase(TestCase):

    def setUp(self):
        random.seed(0)
        ctor.test_setup()

    def tearDown(self):
        ctor.test_teardown()

    def disable_t0(self):
        """Keep this test on the solver. Mirrors VscTestCase.disable_t0 -- see
        there for why a back-end test needs it."""
        import vsc.model.randomizer as _rnd
        saved = _rnd._T0_ENABLED
        _rnd._T0_ENABLED = False

        def _restore():
            _rnd._T0_ENABLED = saved
        self.addCleanup(_restore)
