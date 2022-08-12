'''
Created on Apr 10, 2020

@author: ballance
'''
import vsc
from .vsc_test_case import VscTestCase

class TestCovergroupParameterized(VscTestCase):
    
    def test_diff_coverpoints(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, create_cpb):
                self.with_sample(
                    a=vsc.uint32_t(),
                    b=vsc.uint32_t()
                    )
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    bins_a=vsc.bin_array([], [1,16])))
                
                if create_cpb:
                    self.b_cp = vsc.coverpoint(self.b, bins=dict(
                        bins_b=vsc.bin_array([], [1,16])))
                    
        cg1 = my_cg(False)
        cg2 = my_cg(True)
        
        cg1.sample(1, 0)
        cg2.sample(0, 1)

        report = vsc.get_coverage_report_model()

        # There are two covergroup types        
        self.assertEqual(2, len(report.covergroups))
                    
                