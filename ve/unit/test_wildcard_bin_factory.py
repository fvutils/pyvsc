'''
Created on Jul 23, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase
from vsc.impl.wildcard_bin_factory import WildcardBinFactory

class TestWildcardBinFactory(VscTestCase):
    
    def test_bin_expr(self):
        value, mask = WildcardBinFactory.str2bin("0b0010XXXX")
        self.assertEqual(value, 0b00100000)
        self.assertEqual(mask, 0b11110000)
        
    def test_oct_expr(self):
        value, mask = WildcardBinFactory.str2bin("0o0010XXXX")
        self.assertEqual(value, 0o00100000)
        self.assertEqual(mask, 0o77770000)
        
    def test_hex_expr(self):
        value, mask = WildcardBinFactory.str2bin("0x00?01234")
        self.assertEqual(value, 0x00001234)
        self.assertEqual(mask, 0xFF0FFFFF)
    
    def test_binlist_lsbligned(self):
        bins = WildcardBinFactory.valmask2binlist(0x12345600, 0xFFFFFF00)
        
    def test_binlist_mid(self):
        bins = WildcardBinFactory.valmask2binlist(0x12345067, 0xFFFFF0FF)
        
    def test_binlist_mid_lsb(self):
        ranges = bins = WildcardBinFactory.valmask2binlist(0x12345060, 0xFFFFF0F0)
        self.assertEqual(len(ranges), 16)
        
        for i,r in enumerate(ranges):
            exp_v = 0x12345060 | (i << 8)
            
            self.assertEqual(r[0], exp_v)
            self.assertEqual(r[1], exp_v | 0xF)
            
        