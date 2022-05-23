'''
Created on Mar 15, 2020

@author: ballance
'''
from unittest.case import TestCase
from vsc1.impl import ctor
import vsc
from vsc1.impl.coverage_registry import CoverageRegistry

class TestTypeCoverage(TestCase):
    
    def setUp(self):
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()

    def test_type_cg_smoke(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()
                    ))
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a_bins = vsc.bin_array([], [1,16])
                    ))
                self.b_cp = vsc.coverpoint(self.b, bins=dict(
                    b_bins = vsc.bin_array([], [1,16])
                    ))

        cg1 = my_cg()
        cg2 = my_cg()
        
        for i in range(16):
            cg1.sample(i+1, 0)
            
        for i in range(16):
            cg1.sample(0, i+1)
            
        rgy = CoverageRegistry.inst()

        self.assertTrue("my_cg" in rgy.types())
        self.assertEqual(1, len(rgy.types()))
        self.assertEqual(1, len(rgy.instances("my_cg")))
        
        cg_tm = rgy.instances("my_cg")[0]
        self.assertEqual(cg_tm.get_coverage(), 100)

    def test_type_cg_param(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, t):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()
                    ))

                if t == 0:                
                    self.a_cp = vsc.coverpoint(self.a, bins=dict(
                        a_bins = vsc.bin_array([], [1,16])
                        ))
                else:
                    self.b_cp = vsc.coverpoint(self.b, bins=dict(
                        b_bins = vsc.bin_array([], [1,16])
                        ))

        cg1 = my_cg(0)
        cg2 = my_cg(1)
        
        for i in range(16):
            cg1.sample(i+1, 0)
            
        for i in range(16):
            cg1.sample(0, i+1)
            
        rgy = CoverageRegistry.inst()

        self.assertTrue("my_cg" in rgy.types())
        self.assertEqual(1, len(rgy.types()))
        self.assertEqual(2, len(rgy.instances("my_cg")))
        
        cg_tm = rgy.instances("my_cg")[0]
        self.assertEqual(cg_tm.get_coverage(), 100)
        