'''
Created on Jul 19, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestLint(VscTestCase):
    
    def test_width_literal_error(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a == 500
                
        i = my_c()
        try:
            i.randomize(lint=1)
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            pass