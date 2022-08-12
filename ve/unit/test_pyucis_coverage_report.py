'''
Created on Apr 7, 2020

@author: ballance
'''
from _datetime import datetime
from ucis import UCIS_TESTSTATUS_OK
from ucis.mem.mem_factory import MemFactory
from ucis.report.coverage_report_builder import CoverageReportBuilder
from ucis.test_data import TestData

import vsc
from vsc1.impl.coverage_registry import CoverageRegistry
from vsc1.visitors.coverage_save_visitor import CoverageSaveVisitor
from .vsc_test_case import VscTestCase


class TestPyUCISCoverageReport(VscTestCase):
    
    def get_ucis_report(self):
        covergroups = CoverageRegistry.inst().covergroup_types()
        db = MemFactory.create()
        cov_visitor = CoverageSaveVisitor(db)
        cov_visitor.save(
            TestData(
                UCIS_TESTSTATUS_OK, 
                "UCIS:simulator",
                datetime.now().strftime("%Y%m%d%H%M%S")),
            covergroups)
        
        return CoverageReportBuilder.build(cov_visitor.db)
        
    
    def test_even_weights(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, a, b):
                self.a_cp = vsc.coverpoint(a, bins=dict(
                    a_arr = vsc.bin_array([], [1,8])
                    ))
                self.b_cp = vsc.coverpoint(b, bins=dict(
                    b_arr = vsc.bin_array([], [1,4])
                    ))

        a = 0
        b = 0                
        cg_i = my_cg(lambda:a, lambda:b)
        
        for i in range(1,5):
            a=i
            cg_i.sample()
            
        for i in range(1,5):
            b=i
            cg_i.sample()
            
        report = self.get_ucis_report()
        self.assertEqual(1, len(report.covergroups))
        # Coverpoints have equal weights, so we expect to have 75% coverage
        self.assertEqual(75, report.coverage)

    def disabled_test_uneven_weights(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, a, b):
                self.a_cp = vsc.coverpoint(a, 
                    options=dict(weight=8),
                    bins=dict(
                        a_arr = vsc.bin_array([], [1,8])
                    )
                )
                self.b_cp = vsc.coverpoint(b, 
                    options=dict(weight=4),
                    bins=dict(
                        b_arr = vsc.bin_array([], [1,4])
                    )
                )

        a = 0
        b = 0                
        cg_i = my_cg(lambda:a, lambda:b)
        
        for i in range(1,5):
            a=i
            cg_i.sample()
            
        for i in range(1,5):
            b=i
            cg_i.sample()
            
        report = self.get_ucis_report()
        self.assertEqual(1, len(report.covergroups))
        # Coverpoints have proportionate weights, so we expect to have
        # (50*8+100*4)/12 => 66.67% coverage
        self.assertEqual(round((50*8+100*4)/12,2), report.coverage)        

