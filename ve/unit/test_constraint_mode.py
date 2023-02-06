'''
Created on Mar 3, 2020

@author: ballance
'''
import vsc
from unittest.case import TestCase
from vsc_test_case import VscTestCase

class TestConstraintMode(VscTestCase):
    
    def test_smoke(self):

        # Test that bounds are re-calculated correctly when disabling constraints.
        # a_zero_c would set bounds to zero, but disabling that constraint zero
        # should be *nigh* impossible for 1024 bits.
        # See: https://github.com/fvutils/pyvsc/issues/173
        @vsc.randobj
        class my_item_0_c(object):

            def __init__(self):
                self.a = vsc.rand_bit_t(1024)

            @vsc.constraint
            def a_zero_c(self):
                self.a == 0

        it = my_item_0_c()

        it.a_zero_c.constraint_mode(False)

        for i in range(16):
            it.randomize()
            self.assertNotEqual(it.a, 0)

        @vsc.randobj
        class my_item_1_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def ab_eq_c(self):
                self.a == self.b
                
            @vsc.constraint
            def ab_ne_c(self):
                self.a != self.b

        it = my_item_1_c()

        for i in range(16):
            it.ab_eq_c.constraint_mode(True)
            it.ab_ne_c.constraint_mode(False)
            it.randomize()
            self.assertEqual(it.a, it.b)
            
            it.ab_eq_c.constraint_mode(False)
            it.ab_ne_c.constraint_mode(True)
            it.randomize()
            self.assertNotEqual(it.a, it.b)
