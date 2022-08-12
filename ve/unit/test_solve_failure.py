'''
Created on Oct 25, 2020

@author: ballance
'''
from enum import IntEnum, auto

import vsc
from .vsc_test_case import VscTestCase


class TestSolveFailure(VscTestCase):
    
    def test_fail_enum(self):
        
        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj(srcinfo=True)
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
            with it.randomize_with(solve_fail_debug=True):
                it.a == 2
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))


    def test_fail_constraint_pair(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                self.d = vsc.rand_uint8_t()
                
            @vsc.constraint
            def abcd_c(self):
                self.c > self.b
                self.a < self.b
                self.c < self.a
                self.c < 10
                self.a > 0
                self.b <= 20
                
        it = my_c()

        try:        
            it.randomize()
            self.fail("Expected a solve failure")
        except vsc.SolveFailure as e:
            print("Exception: " + str(e.diagnostics))
    