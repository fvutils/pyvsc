'''
Created on Oct 25, 2020

@author: ballance
'''
from enum import IntEnum, auto

import vsc
from vsc_test_case import VscTestCase


class TestSolveFailure(VscTestCase):
    
    def test_fail_enum(self):
        
        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.e = vsc.rand_enum_t(my_e)
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a == 1
                with vsc.if_then(self.a == 2):
                    self.e == my_e.A
                
        it = my_c()

        try:        
            with it.randomize_with():
                it.a == 2
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            print("Exception: " + str(e))

    