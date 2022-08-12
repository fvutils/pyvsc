'''
Created on Apr 29, 2021

@author: mballance
'''
import vsc
from .vsc_test_case import VscTestCase

class TestCoverageOptions(VscTestCase):
    
    def test_coverpoint_atleast_option(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.options.at_least = 2
                
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8),
                    })
                self.cp2 = vsc.coverpoint(self.b, bins={
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                
        cg_i = cg()
        
        cg_i.sample(1, 1)
        cg_i.sample(1, 2)
        cg_i.sample(2, 4)
        cg_i.sample(2, 8)
        
        vsc.report_coverage(details=True)
                