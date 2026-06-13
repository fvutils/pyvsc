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
