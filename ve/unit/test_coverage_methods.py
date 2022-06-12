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
            
        # First, confirm that the bins have been hit
        model = cg_i.get_model()
        cp = model.coverpoint_l[0]
        
        self.assertEqual(cp.get_n_bins(), 16)
        
        for i in range(8):
            self.assertEqual(1, cp.get_bin_hits(i))
            
        self.assertEqual(cg_i.a_cp.get_coverage(), 50.0)
        
    def test_example(self):
        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=vsc.bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8)
                    })

        cg1 = my_covergroup()
        cg2 = my_covergroup()
       
        cg1.sample(1)
        self.assertEqual(cg1.get_coverage(), 25.0)
        self.assertEqual(cg1.get_inst_coverage(), 25.0)
        self.assertEqual(cg2.get_inst_coverage(), 0.0)
        print("Type=%f cg1=%f cg2=%f" % (
          cg1.get_coverage(),
          cg1.get_inst_coverage(),
          cg2.get_inst_coverage()))
          
        cg2.sample(2)
        self.assertEqual(cg1.get_coverage(), 50.0)
        self.assertEqual(cg1.get_inst_coverage(), 25.0)
        self.assertEqual(cg2.get_inst_coverage(), 25.0)
        print("Type=%f cg1=%f cg2=%f" % (
          cg1.get_coverage(),
          cg1.get_inst_coverage(),
          cg2.get_inst_coverage()))

    def test_example_1(self):
        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=vsc.bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8)
                    })

        cg1 = my_covergroup()
        cg2 = my_covergroup()
       
        cg1.sample(1)
        cg2.sample(2)
        
        print("==== Without Details ===")
        vsc.report_coverage()
        print()
        print("==== With Details ===")
        vsc.report_coverage(details=True)

