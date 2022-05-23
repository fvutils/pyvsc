'''
Created on Mar 24, 2020

@author: ballance
'''
from _io import StringIO
import sys

from ucis.report import coverage_report_builder
from ucis.report.coverage_report_builder import CoverageReportBuilder
from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
from ucis.xml.xml_factory import XmlFactory
import vsc
from vsc import bin_array
from vsc_test_case import VscTestCase


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
        

    def test_single_type_two_inst_xml(self):
        
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
        
        for i in range(8):
            my_cg_1.sample(2*i, 0)
            if i%2 == 0:
                my_cg_1.sample(2*i, 0)
            my_cg_2.sample(2*i+1, 0)
            if i%3 == 0:
                my_cg_2.sample(2*i+1, 0)
                my_cg_2.sample(2*i+1, 0)

        print(">================== Text Report ======================")
        print("Report:\n" + vsc.get_coverage_report(True))
        print("<================== Text Report ======================")
        out = StringIO()
        vsc.write_coverage_db("cov.xml")
        print(">================== Write XML ========================")
        vsc.write_coverage_db(out)
        print("<================== Write XML ========================")
        db = XmlFactory.read(out)
        print(">================== Build Report =====================")
        report = CoverageReportBuilder.build(db)
        print("<================== Build Report =====================")
        print(">================== Text Reporter ====================")
        reporter = TextCoverageReportFormatter(report, sys.stdout)
        print("<================== Text Reporter ====================")
        reporter.details = True
        print(">================== XML Report =======================")
        reporter.report()
        print("<================== XML Report =======================")
        