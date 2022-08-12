'''
Created on Apr 11, 2020

@author: ballance
'''
from .vsc_test_case import VscTestCase
import vsc

class TestCovergroupOptions(VscTestCase):
    
    def test_comment(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, a, b):
                
                self.a_cp = vsc.coverpoint(a, cp_t=vsc.uint8_t())
                self.b_cp = vsc.coverpoint(b, cp_t=vsc.uint8_t())

        a = 0
        b = 0                
        cg1 = my_cg(lambda:a, lambda:b)
        cg1.options.name = "my_cg1"
        cg1.options.comment = "cg1"

    def test_covergroup_atleast(self):
        
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
        report = vsc.get_coverage_report_model()
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[0].coverage, 50.0)
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[1].coverage, 0.0)
        
    def test_coverpoint_atleast(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.options.at_least = 2
                
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8),
                    }, options=dict(at_least=1))
                self.cp2 = vsc.coverpoint(self.b, bins={
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                
        cg_i = cg()
        
        cg_i.sample(1, 1)
        cg_i.sample(2, 2)
        cg_i.sample(4, 4)
        cg_i.sample(8, 8)
        cg_i.sample(1, 1)
        cg_i.sample(2, 2)
        
        vsc.report_coverage(details=True)
        report = vsc.get_coverage_report_model()
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[0].coverage, 100.0)
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[1].coverage, 50.0)

    def test_coverpoint_weight(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8),
                    }, options=dict(weight=1))
                self.cp2 = vsc.coverpoint(self.b, bins={
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    }, options=dict(weight=0))
                
        cg_i = cg()
        
        cg_i.sample(1, 1)
        cg_i.sample(2, 2)
        cg_i.sample(4, 1)
        cg_i.sample(8, 2)
        
        vsc.report_coverage(details=True)
        report = vsc.get_coverage_report_model()
        self.assertEqual(report.covergroups[0].covergroups[0].coverage, 100.0)
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[0].coverage, 100.0)
        self.assertEqual(report.covergroups[0].covergroups[0].coverpoints[1].coverage, 50.0)

        