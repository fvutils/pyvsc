'''
Created on Mar 7, 2020

@author: ballance
'''

from unittest import TestCase
from vsc.impl import ctor
import random


class VscTestCase(TestCase):
   
    def setUp(self):
        random.seed(0)
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()

    def disable_t0(self):
        """Keep this test on the solver.

        The T0 tier (vsc.model.separability) answers a separable, bound-only
        RandSet without calling a back-end at all. That is correct and is the
        point of the tier — but it makes a test whose *subject* is back-end
        machinery (merged solve, differential cross-check, fallback reason
        codes) observe nothing. Such a test calls this to keep its workload on
        the solver; it is not a workaround for a T0 defect.
        """
        import vsc.model.randomizer as _rnd
        saved = _rnd._T0_ENABLED
        _rnd._T0_ENABLED = False

        def _restore():
            _rnd._T0_ENABLED = saved
        self.addCleanup(_restore)