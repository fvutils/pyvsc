'''
Created on May 8, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestCoverageGuided(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint16_t()
                self.b = vsc.rand_uint16_t()
                
        @vsc.covergroup
        class cg_c(object):
            
            def __init__(self):
                self.with_sample(it=cls())
                
                self.cp_a = vsc.coverpoint(self.it.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                self.cp_b = vsc.coverpoint(self.it.b, bins={
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                
        cg = cg_c()
        c = cls()

        for i in range(8):
            c.randomize(cg=cg)
            print("[%d] a=%d b=%d" % (i, c.a, c.b))
            vsc.report_coverage(details=True)
            
        