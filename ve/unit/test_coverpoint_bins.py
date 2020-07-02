'''
Created on Jul 1, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestCoverpointBins(VscTestCase):
    
    def test_bin_array_partition(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        a1=vsc.bin_array([4], (0,16))
                        ))
                
        cg = my_cg()
        cg.sample(0)
        cg.sample(3)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 25)
        cg.sample(4)
        cg.sample(7)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 50)
        
        