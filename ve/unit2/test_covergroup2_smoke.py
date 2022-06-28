'''
Created on Jun 23, 2022

@author: mballance
'''
import vsc2
from vsc_test_case2 import VscTestCase2
from typing import Callable

class TestCovergroup2Smoke(VscTestCase2):
    
    def test_smoke1(self):
        
        @vsc2.covergroup(
            sample=vsc2.sample[dict(
                a=vsc2.bit_t[32],
                b=vsc2.int_t[8])])
        class my_cg(object):
            pass
            a : int
            cp : cp_def
            
            def cp_def(self):
                pass
            
        @vsc2.covergroup
        class my_cg2(object):
            
            def __init__(self):
                self.cp = vsc2.coverpoint(1)
            
        
        