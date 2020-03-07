'''
Created on Mar 6, 2020

@author: ballance
'''
import vsc
from unittest.case import TestCase
from vsc_test_case import VscTestCase

class TestCoverageMethods(VscTestCase):

    def test_coverpoint_get_coverage(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                
                self.with_sample(dict(
                    a=vsc.bit_t(8)
                ))
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.bin_array([], [1,16])
                    )
                )

        cg_i = my_cg()
        for i in range(8):
            cg_i.sample(i+1)
            
        cg_i.dump()
            
        # First, confirm that the bins have been hit
        model = cg_i.get_model()
        cp = model.coverpoint_l[0]
        
        self.assertEqual(cp.get_n_bins(), 16)
        
        for i in range(8):
            self.assertEqual(1, cp.get_bin_hits(i))
            
        self.assertEqual(cg_i.a_cp.get_coverage(), 0.5)
