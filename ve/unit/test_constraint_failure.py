'''
Created on Sep 10, 2020

@author: ballance
'''

import vsc
from vsc_test_case import VscTestCase

class TestConstraintFailure(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a > 5
                self.b < 5
                self.a < self.b
                
        it = my_c()

        try:        
            it.randomize()
            self.fail("no exception thrown")
        except vsc.SolveFailure as e:
            pass
        