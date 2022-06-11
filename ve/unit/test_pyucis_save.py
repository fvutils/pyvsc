'''
Created on Mar 14, 2020

@author: ballance
'''

from _io import StringIO
from ucis import UCIS_TESTSTATUS_OK
from ucis.lib import libucis
from ucis.lib.LibFactory import LibFactory
from ucis.lib.lib_ucis import LibUCIS
from ucis.mem.mem_factory import MemFactory
from ucis.test_data import TestData
from ucis.xml.xml_reader import XmlReader
from ucis.xml.xml_writer import XmlWriter
from unittest import TestCase

import vsc
from vsc.impl import ctor
from vsc.impl.coverage_registry import CoverageRegistry
from vsc.visitors.coverage_save_visitor import CoverageSaveVisitor
from ucis.xml.xml_factory import XmlFactory
from ucis.report.coverage_report_builder import CoverageReportBuilder
from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
import sys


class TestPyUcisSave(TestCase):
    
    def setUp(self):
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()
    
    def test_simple_dump(self):
        
        @vsc.covergroup
        class my_covergroup(object):
            
            def __init__(self):
                
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()
                    ))
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a_bins =  vsc.bin_array([], [1,8])
                    ))
                
                self.b_cp = vsc.coverpoint(self.b, bins=dict(
                    b_bins = vsc.bin_array([], [1,8])
                    ))

        cg_1 = my_covergroup()
        
        cg_1.sample(1, 2)
        cg_1.sample(2, 1)
        cg_1.sample(4, 2)
        
        cg_2 = my_covergroup()
        
        cg_2.sample(5, 4)
        cg_2.sample(6, 2)
        cg_2.sample(7, 8)

        db = MemFactory.create()
        v = CoverageSaveVisitor(db)

        td = TestData(
            teststatus=UCIS_TESTSTATUS_OK,
            toolcategory="UCIS:simulator",
            date="20200101132000")        
        v.save(td, CoverageRegistry.inst().covergroup_types())
        db.close()

        out = StringIO()        
        writer = XmlWriter()
        writer.write(out, db)

        print("Output:\n" + out.getvalue())        

        xmlin = StringIO(out.getvalue())        
        XmlReader.validate(xmlin)

    def test_cross(self):
        @vsc.covergroup
        class my_covergroup(object):

            def __init__(self): 
                super().__init__()
                self.a=None
                self.b=None
                self.cp1 = vsc.coverpoint(lambda:self.a,
                    bins=dict(
                        a = vsc.bin_array([], [0,15])
                    ))

                self.cp2 = vsc.coverpoint(lambda:self.b, bins=dict(
                    b = vsc.bin_array([], [0,15])
                    ))
                self.cross = vsc.cross([self.cp1, self.cp2])


            #a = 0;
            #b = 0;

        cg = my_covergroup()

        cg.a = 0 
        cg.b = 0
        print("A: ",str(cg.a), " B: ", str(cg.b))
        cg.sample() # Hit the first bin of cp1 and cp2  

            
        report = vsc.get_coverage_report()
        print("Report:\n" + report)
        out = StringIO()
        vsc.write_coverage_db("cov.xml")
        print(">================== Write XML ========================")
        vsc.write_coverage_db(out)
        print("<================== Write XML ========================")
        db = XmlFactory.read(StringIO(out.getvalue()))
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

        