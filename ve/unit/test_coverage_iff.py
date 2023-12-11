'''
Created on Apr 14, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestCoverageIFF(VscTestCase):
    
    def test_class_field_iff(self):

        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict( a=vsc.uint8_t(),b=vsc.uint8_t()))
                self.cp1 = vsc.coverpoint(self.a, iff=(self.b == 9), bins={ 
                    "a" : vsc.bin_array([], 1, 2, 4), 
                    "b" : vsc.bin_array([4], [8,16])})

        my_cg_1 = my_cg()

        my_cg_1.sample(1, 0)
        my_cg_1.sample(2, 9)
        my_cg_1.sample(4, 0)

        report = vsc.get_coverage_report_model()
        str_report = vsc.get_coverage_report(details=True)
        print("Report:\n" + str_report)
        
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints[0].bins), 7)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[0].count, 0)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[1].count, 1)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[2].count, 0)

    def test_lambda_iff(self):

        @vsc.covergroup
        class my_cg(object):
            def __init__(self, sample_c):
                self.with_sample(dict( a=vsc.uint8_t(),b=vsc.uint8_t()))
                self.cp1 = vsc.coverpoint(self.a, iff=sample_c, bins={ 
                    "a" : vsc.bin_array([], 1, 2, 4), 
                    "b" : vsc.bin_array([4], [8,16])})

        en = True

        my_cg_1 = my_cg(lambda : en)

        en = False
        my_cg_1.sample(1, 0)
        en = True
        my_cg_1.sample(2, 9)
        en = False
        my_cg_1.sample(4, 0)

        report = vsc.get_coverage_report_model()
        str_report = vsc.get_coverage_report(details=True)
        print("Report:\n" + str_report)
        
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints[0].bins), 7)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[0].count, 0)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[1].count, 1)
        self.assertEqual(report.covergroups[0].coverpoints[0].bins[2].count, 0)        

    def test_class_field_cross_iff(self):

        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict( 
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t(),
                    c=vsc.bool_t()))
                self.cp1 = vsc.coverpoint(self.a, bins={ 
                    "a" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                self.cp2 = vsc.coverpoint(self.b, bins={ 
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    })
                self.cr = vsc.cross([self.cp1, self.cp2], iff=self.c)
#                self.cr = vsc.cross([self.cp1, self.cp2])

        my_cg_1 = my_cg()

        for i in [1,2,4,8]:
            for j in [1,2,4,8]:
                my_cg_1.sample(i, j, i==j)

        report = vsc.get_coverage_report_model()
        str_report = vsc.get_coverage_report(details=True)
        print("Report:\n" + str_report)
        
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints), 2)
        self.assertEqual(len(report.covergroups[0].crosses), 1)
        for ii,i in enumerate([1,2,4,8]):
            for ji,j in enumerate([1,2,4,8]):
                if i == j:
                    self.assertEqual(report.covergroups[0].crosses[0].bins[4*ii+ji].count, 1)
                else:
                    self.assertEqual(report.covergroups[0].crosses[0].bins[4*ii+ji].count, 0)
        
        