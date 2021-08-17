'''
Created on Jul 23, 2021

@author: mballance
'''

import vsc
from vsc_test_case import VscTestCase

class TestCoverageWildcardBins(VscTestCase):
    
    def test_single_wildcard_bin_1(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin("0x8x")))
                
        cg_i = cg()
        cg_i.sample(0)
        self.assertEqual(cg_i.get_coverage(), 0.0)
        cg_i.sample(0x81)
        self.assertEqual(cg_i.get_coverage(), 100.0)
        
    def test_single_wildcard_bin_1_1(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a1=vsc.bit_t(8), a2=vsc.bit_t(8)))
                
                self.cp_a1 = vsc.coverpoint(self.a1, bins=dict(
                    a=vsc.wildcard_bin("0x8x", "0x6x")))
                self.cp_a2 = vsc.coverpoint(self.a2, bins=dict(
                    a=vsc.wildcard_bin("0x8x", "0x6x")))
                
        cg_i = cg()
        cg_i.sample(0, 0)
        self.assertEqual(cg_i.cp_a1.get_coverage(), 0.0)
        self.assertEqual(cg_i.cp_a2.get_coverage(), 0.0)
        
        cg_i.sample(0x81, 0)
        self.assertEqual(cg_i.cp_a1.get_coverage(), 100.0)        
        
        self.assertEqual(cg_i.cp_a2.get_coverage(), 0.0)
        cg_i.sample(0, 0x61)
        self.assertEqual(cg_i.cp_a2.get_coverage(), 100.0)        
        
    def test_single_wildcard_bin_2(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin((0x80,0xF0))
                    ))
                
        cg_i = cg()
        cg_i.sample(0)
        self.assertEqual(cg_i.get_coverage(), 0.0)
        cg_i.sample(0x81)
        self.assertEqual(cg_i.get_coverage(), 100.0)

    def test_array_wildcard_bin_1(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin_array([], "0x8x")
                    ))
                
        cg_i = cg()
        cg_i.sample(0)
        self.assertEqual(cg_i.get_coverage(), 0.0)

        for i in range(16):        
            cg_i.sample(0x80+i)
            self.assertEqual(cg_i.get_coverage(), 100*((1+i)/16))

    def test_array_wildcard_bin_2(self):
        @vsc.covergroup
        class cg(object):
        
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
        
                self.cp_a = vsc.coverpoint(lambda: self.a[7:0], bins=dict(
                    a=vsc.wildcard_bin_array([], "0b1011011x", "0b0x101010")
                    ))
        
        obj1 = cg()


        