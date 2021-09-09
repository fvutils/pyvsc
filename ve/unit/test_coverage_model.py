'''
Created on Mar 7, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_ref_model import ExprRefModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverage_options_model import CoverageOptionsModel

class TestCoverageModel(VscTestCase):
    
    def test_coverpoint_array_bin(self):
        
        cg = CovergroupModel("cg")

        a = 0        
        a_cp = CoverpointModel(
            ExprRefModel(lambda: a, 32, False), "a_cp",
            CoverageOptionsModel())
        cg.add_coverpoint(a_cp)
        
        bins = a_cp.add_bin_model(CoverpointBinArrayModel("a", 0, 15))
        
        cg.finalize()
        
        for i in range(8):
            a = i
            cg.sample()
            
        for i in range(16):
            if (i < 8):
                self.assertEqual(a_cp.get_bin_hits(i), 1)
            else:
                self.assertEqual(a_cp.get_bin_hits(i), 0)
                
        self.assertEqual(a_cp.get_coverage(), 50.0)
        self.assertEqual(cg.get_coverage(), 50.0)
            
                             
        
        