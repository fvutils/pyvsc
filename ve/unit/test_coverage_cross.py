'''
Created on Mar 13, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase
from enum import IntEnum, IntFlag, Flag, auto, Enum
import vsc
from vsc_test_case import VscTestCase
import random


class TestCoverageCross(VscTestCase):
    
    def test_bin_names_int_enum(self):
        
        class my_e_1(IntEnum):
            A = auto()
            B = auto()
            
        class my_e_2(IntEnum):
            C = auto()
            D = auto()

        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, v1,v2):
                
                self.cp1 = vsc.coverpoint(v1, cp_t=vsc.enum_t(my_e_1))
                self.cp2 = vsc.coverpoint(v2, cp_t=vsc.enum_t(my_e_2))
                self.cp1X2 = vsc.cross([self.cp1, self.cp2])
                
        for i in range(16):
#            A=random.rand(2)
#            B=random.rand(2)
#            C=random.rand(2)
#            D=random.rand(2)
            v1 = my_e_1.A                
            v2 = my_e_2.C                
            cg = my_cg(lambda:v1,lambda:v2)
            cg.sample()
            v1 = my_e_1.B
            v2 = my_e_2.D                
            cg.sample()
        
        vsc.report_coverage(details=True)
        report = vsc.get_coverage_report_model()
        
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints), 2)
        self.assertEqual(len(report.covergroups[0].crosses), 1)
        self.assertEqual(report.covergroups[0].coverpoints[0].coverage, 100)
        self.assertEqual(report.covergroups[0].coverpoints[1].coverage, 100)
        self.assertEqual(report.covergroups[0].crosses[0].coverage, 50)

