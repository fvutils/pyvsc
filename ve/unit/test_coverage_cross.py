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

    def test_nested_cross_basic(self):
        """Test basic nested cross: cross of (cross + coverpoint)"""
        
        @vsc.covergroup
        class nested_cross_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t(),
                    c = vsc.uint8_t()
                ))

                self.cp_a = vsc.coverpoint(self.a, bins={"a_bins": vsc.bin_array([4], [0, 255])})
                self.cp_b = vsc.coverpoint(self.b, bins={"b_bins": vsc.bin_array([4], [0, 255])})
                self.cp_c = vsc.coverpoint(self.c, bins={"c_bins": vsc.bin_array([4], [0, 255])})

                # Standard cross
                self.cross_ab = vsc.cross([self.cp_a, self.cp_b])

                # Nested cross: cross of a cross and a coverpoint
                # This should create a 3D matrix (A x B x C)
                self.cross_abc = vsc.cross([self.cross_ab, self.cp_c])

        cg = nested_cross_cg()
        
        # Sample various combinations
        cg.sample(a=10, b=20, c=30)
        cg.sample(a=100, b=150, c=200)
        cg.sample(a=200, b=100, c=50)
        
        # Verify that the nested cross was created correctly
        # The cross_abc should have 3 coverpoints (a, b, c) flattened
        self.assertEqual(len(cg.cross_abc.target_l), 3)
        self.assertEqual(cg.cross_abc.target_l[0], cg.cp_a)
        self.assertEqual(cg.cross_abc.target_l[1], cg.cp_b)
        self.assertEqual(cg.cross_abc.target_l[2], cg.cp_c)

    def test_nested_cross_two_crosses(self):
        """Test cross of two crosses"""
        
        @vsc.covergroup
        class two_cross_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t(),
                    c = vsc.uint8_t(),
                    d = vsc.uint8_t()
                ))

                self.cp_a = vsc.coverpoint(self.a, bins={"a_bins": vsc.bin_array([2], [0, 255])})
                self.cp_b = vsc.coverpoint(self.b, bins={"b_bins": vsc.bin_array([2], [0, 255])})
                self.cp_c = vsc.coverpoint(self.c, bins={"c_bins": vsc.bin_array([2], [0, 255])})
                self.cp_d = vsc.coverpoint(self.d, bins={"d_bins": vsc.bin_array([2], [0, 255])})

                # Two crosses
                self.cross_ab = vsc.cross([self.cp_a, self.cp_b])
                self.cross_cd = vsc.cross([self.cp_c, self.cp_d])

                # Cross of crosses: creates 4D matrix (A x B x C x D)
                self.cross_abcd = vsc.cross([self.cross_ab, self.cross_cd])

        cg = two_cross_cg()
        
        # Sample various combinations
        cg.sample(a=10, b=20, c=30, d=40)
        cg.sample(a=200, b=220, c=230, d=240)
        
        # Verify that the nested cross flattened correctly
        self.assertEqual(len(cg.cross_abcd.target_l), 4)
        self.assertEqual(cg.cross_abcd.target_l[0], cg.cp_a)
        self.assertEqual(cg.cross_abcd.target_l[1], cg.cp_b)
        self.assertEqual(cg.cross_abcd.target_l[2], cg.cp_c)
        self.assertEqual(cg.cross_abcd.target_l[3], cg.cp_d)

    def test_nested_cross_deep(self):
        """Test deeply nested crosses (3+ levels)"""
        
        @vsc.covergroup
        class deep_cross_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t(),
                    c = vsc.uint8_t(),
                    d = vsc.uint8_t()
                ))

                self.cp_a = vsc.coverpoint(self.a, bins={"a_bins": vsc.bin_array([2], [0, 255])})
                self.cp_b = vsc.coverpoint(self.b, bins={"b_bins": vsc.bin_array([2], [0, 255])})
                self.cp_c = vsc.coverpoint(self.c, bins={"c_bins": vsc.bin_array([2], [0, 255])})
                self.cp_d = vsc.coverpoint(self.d, bins={"d_bins": vsc.bin_array([2], [0, 255])})

                # Build nested crosses progressively
                self.cross_ab = vsc.cross([self.cp_a, self.cp_b])
                self.cross_abc = vsc.cross([self.cross_ab, self.cp_c])
                self.cross_abcd = vsc.cross([self.cross_abc, self.cp_d])

        cg = deep_cross_cg()
        
        # Sample
        cg.sample(a=10, b=20, c=30, d=40)
        
        # Verify deep flattening
        self.assertEqual(len(cg.cross_abcd.target_l), 4)
        self.assertEqual(cg.cross_abcd.target_l[0], cg.cp_a)
        self.assertEqual(cg.cross_abcd.target_l[1], cg.cp_b)
        self.assertEqual(cg.cross_abcd.target_l[2], cg.cp_c)
        self.assertEqual(cg.cross_abcd.target_l[3], cg.cp_d)

    def test_nested_cross_with_options(self):
        """Test nested cross with options"""
        
        @vsc.covergroup
        class nested_cross_options_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t(),
                    c = vsc.uint8_t()
                ))

                self.cp_a = vsc.coverpoint(self.a, bins={"a_bins": vsc.bin_array([2], [0, 255])})
                self.cp_b = vsc.coverpoint(self.b, bins={"b_bins": vsc.bin_array([2], [0, 255])})
                self.cp_c = vsc.coverpoint(self.c, bins={"c_bins": vsc.bin_array([2], [0, 255])})

                self.cross_ab = vsc.cross([self.cp_a, self.cp_b])
                
                # Nested cross with options
                self.cross_abc = vsc.cross(
                    [self.cross_ab, self.cp_c],
                    options=dict(at_least=2)
                )

        cg = nested_cross_options_cg()
        cg.sample(a=10, b=20, c=30)
        
        # Verify structure
        self.assertEqual(len(cg.cross_abc.target_l), 3)
        # Verify options were set
        self.assertIsNotNone(cg.cross_abc.options)

