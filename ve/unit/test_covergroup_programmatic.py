'''
Created on Apr 10, 2020

@author: ballance
'''
import vsc
from .vsc_test_case import VscTestCase

class TestCovergroupProgrammatic(VscTestCase):
    
    def disabled_test_programmatic_coverpoints(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, n_cp):
                var_names = ["a", "b", "c", "d"]

                # Create a variable for all possible variables
                parameters = dict()
                parameters.update(map(lambda n:(n,vsc.uint8_t()), var_names))
                self.with_sample(parameters)

                self.coverpoints = []                
                for i in range(n_cp):
                    self.coverpoints.append(
                        vsc.coverpoint(
                            getattr(self, var_names[i]),
                            bins=dict(
                                values=vsc.bin_array([], [1,15]))))
                    
        cg1 = my_cg(2)
        cg2 = my_cg(4)
        
        report = vsc.get_coverage_report_model()
        self.assertEqual(2, report.covergroups)
    
    