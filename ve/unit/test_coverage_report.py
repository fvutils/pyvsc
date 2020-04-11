'''
Created on Mar 24, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc.coverage import bin_array

class TestCoverageReport(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.a_cp = vsc.coverpoint(self.a, bins={
                    "a" : bin_array(4, [1,15])
                    })

        my_cg_1 = my_cg()
        my_cg_2 = my_cg()
        
        for i in range(8):
            my_cg_1.sample(i, 0)
            
        for i in range(16):
            my_cg_2.sample(i, 0)

        report = vsc.get_coverage_report_model()
        
        self.assertEqual(1, len(report.covergroups))
        self.assertEqual(2, len(report.covergroups[0].covergroups))
        self.assertEqual(1, len(report.covergroups[0].covergroups[0].coverpoints))
        self.assertEqual(1, len(report.covergroups[0].covergroups[1].coverpoints))
        
        vsc.report_coverage(details=True)
        
    def test_single_type_two_inst(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.a_cp = vsc.coverpoint(self.a, bins={
                    "a" : bin_array([], [0,15])
                    })

        my_cg_1 = my_cg()
        my_cg_2 = my_cg()
        
        for i in range(16):
            my_cg_1.sample(i, 0)
            
        vsc.report_coverage()
            
        report = vsc.get_coverage_report_model()
        
        
        self.assertEqual(1, len(report.covergroups))
        self.assertEqual(2, len(report.covergroups[0].covergroups))
        self.assertEqual(100, report.covergroups[0].coverage)
        self.assertEqual(100, report.covergroups[0].covergroups[0].coverage)
        self.assertEqual(0, report.covergroups[0].covergroups[1].coverage)
        
    def test_single_type_two_inst_details(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.a_cp = vsc.coverpoint(self.a, bins={
                    "a" : bin_array([], [0,15])
                    })

        my_cg_1 = my_cg()
        my_cg_2 = my_cg()
        
        for i in range(16):
            my_cg_1.sample(i, 0)
            
        report = vsc.get_coverage_report_model()
        
        self.assertEqual(1, len(report.covergroups))
        self.assertEqual(2, len(report.covergroups[0].covergroups))
        self.assertEqual(100, report.covergroups[0].coverage)
        self.assertEqual(100, report.covergroups[0].covergroups[0].coverage)
        self.assertEqual(0, report.covergroups[0].covergroups[1].coverage)
        
    def test_single_type_two_inst_details_text(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.a_cp = vsc.coverpoint(self.a, bins={
                    "a" : bin_array([], [0,15])
                    })

        my_cg_1 = my_cg()
        my_cg_2 = my_cg()
        
        for i in range(16):
            my_cg_1.sample(i, 0)
            
        report = vsc.get_coverage_report()
        print("Report:\n" + report)
        

        