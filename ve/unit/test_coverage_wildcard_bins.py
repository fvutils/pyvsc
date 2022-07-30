'''
Created on Jul 23, 2021

@author: mballance
'''

import time
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
        self.assertEqual(cg_i.cp_a.get_coverage(), 100.0)
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
        
    def test_array_wildcard_bin_3(self):
        import vsc
        
        @vsc.covergroup
        class cg(object):
        
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
        
                self.cp_a = vsc.coverpoint(lambda: self.a[7:0],
                    bins=dict(
                        a=vsc.wildcard_bin_array([], "0b1011011x", "0b0x101010"),
                        b=vsc.wildcard_bin_array([], "0b1011011x", "0b0x10x01x"))
                    )
        
        obj1 = cg()
        model = vsc.get_coverage_report_model()
        self.assertEqual(len(model.covergroups), 1)
        self.assertEqual(len(model.covergroups[0].coverpoints), 1)
        self.assertEqual(len(model.covergroups[0].coverpoints[0].bins), 14)
        vsc.report_coverage(details=True)

    def test_wildcard_bin_perf(self):

        class uut(object):
            def __init__(self):
                self._val = 40

            def exp(self, v1, v2):
                if v2 == 1:
                    return v2
                else:
                    return v1 * self.exp(v1, v2-1)

            @property
            def value(self):
#                if self._val > 10:
#                    self._val = 2
                ret = self.exp(self._val, self._val)
#                self._val += 1
                return ret

        @vsc.covergroup
        class internal_coverage(object):
            def __init__(self,uut):     
                ##Coverpoint with bins for individual carry bits)
                self.caryallcount=vsc.coverpoint(lambda: uut.value , bins={
                    str(63-i) : vsc.wildcard_bin("0b" + "x" * (63-i) + "1" + "x" * (i)) for i in range(64)})

        @vsc.covergroup
        class internal_coverage_split_cp(object):
            def __init__(self,uut):     
                ##Coverpoint with bins for individual carry bits)
                self.cp0 =vsc.coverpoint(lambda: ((uut.value >> 0) & 1), bins={"1" : vsc.bin(1)})
                self.cp1 =vsc.coverpoint(lambda: ((uut.value >> 1) & 1), bins={"1" : vsc.bin(1)})
                self.cp2 =vsc.coverpoint(lambda: ((uut.value >> 2) & 1), bins={"1" : vsc.bin(1)})
                self.cp3 =vsc.coverpoint(lambda: ((uut.value >> 3) & 1), bins={"1" : vsc.bin(1)})
                self.cp4 =vsc.coverpoint(lambda: ((uut.value >> 4) & 1), bins={"1" : vsc.bin(1)})
                self.cp5 =vsc.coverpoint(lambda: ((uut.value >> 5) & 1), bins={"1" : vsc.bin(1)})
                self.cp6 =vsc.coverpoint(lambda: ((uut.value >> 6) & 1), bins={"1" : vsc.bin(1)})
                self.cp7 =vsc.coverpoint(lambda: ((uut.value >> 7) & 1), bins={"1" : vsc.bin(1)})
                self.cp8 =vsc.coverpoint(lambda: ((uut.value >> 8) & 1), bins={"1" : vsc.bin(1)})
                self.cp9 =vsc.coverpoint(lambda: ((uut.value >> 9) & 1), bins={"1" : vsc.bin(1)})
                self.cp10 =vsc.coverpoint(lambda: ((uut.value >> 10) & 1), bins={"1" : vsc.bin(1)})
                self.cp11 =vsc.coverpoint(lambda: ((uut.value >> 11) & 1), bins={"1" : vsc.bin(1)})
                self.cp12 =vsc.coverpoint(lambda: ((uut.value >> 12) & 1), bins={"1" : vsc.bin(1)})
                self.cp13 =vsc.coverpoint(lambda: ((uut.value >> 13) & 1), bins={"1" : vsc.bin(1)})
                self.cp14 =vsc.coverpoint(lambda: ((uut.value >> 14) & 1), bins={"1" : vsc.bin(1)})
                self.cp15 =vsc.coverpoint(lambda: ((uut.value >> 15) & 1), bins={"1" : vsc.bin(1)})
                self.cp16 =vsc.coverpoint(lambda: ((uut.value >> 16) & 1), bins={"1" : vsc.bin(1)})
                self.cp17 =vsc.coverpoint(lambda: ((uut.value >> 17) & 1), bins={"1" : vsc.bin(1)})
                self.cp18 =vsc.coverpoint(lambda: ((uut.value >> 18) & 1), bins={"1" : vsc.bin(1)})
                self.cp19 =vsc.coverpoint(lambda: ((uut.value >> 19) & 1), bins={"1" : vsc.bin(1)})
                self.cp20 =vsc.coverpoint(lambda: ((uut.value >> 20) & 1), bins={"1" : vsc.bin(1)})
                self.cp21 =vsc.coverpoint(lambda: ((uut.value >> 21) & 1), bins={"1" : vsc.bin(1)})
                self.cp22 =vsc.coverpoint(lambda: ((uut.value >> 22) & 1), bins={"1" : vsc.bin(1)})
                self.cp23 =vsc.coverpoint(lambda: ((uut.value >> 23) & 1), bins={"1" : vsc.bin(1)})
                self.cp24 =vsc.coverpoint(lambda: ((uut.value >> 24) & 1), bins={"1" : vsc.bin(1)})
                self.cp25 =vsc.coverpoint(lambda: ((uut.value >> 25) & 1), bins={"1" : vsc.bin(1)})
                self.cp26 =vsc.coverpoint(lambda: ((uut.value >> 26) & 1), bins={"1" : vsc.bin(1)})
                self.cp27 =vsc.coverpoint(lambda: ((uut.value >> 27) & 1), bins={"1" : vsc.bin(1)})
                self.cp28 =vsc.coverpoint(lambda: ((uut.value >> 28) & 1), bins={"1" : vsc.bin(1)})
                self.cp29 =vsc.coverpoint(lambda: ((uut.value >> 29) & 1), bins={"1" : vsc.bin(1)})
                self.cp30 =vsc.coverpoint(lambda: ((uut.value >> 30) & 1), bins={"1" : vsc.bin(1)})
                self.cp31 =vsc.coverpoint(lambda: ((uut.value >> 31) & 1), bins={"1" : vsc.bin(1)})
                self.cp32 =vsc.coverpoint(lambda: ((uut.value >> 32) & 1), bins={"1" : vsc.bin(1)})
                self.cp33 =vsc.coverpoint(lambda: ((uut.value >> 33) & 1), bins={"1" : vsc.bin(1)})
                self.cp34 =vsc.coverpoint(lambda: ((uut.value >> 34) & 1), bins={"1" : vsc.bin(1)})
                self.cp35 =vsc.coverpoint(lambda: ((uut.value >> 35) & 1), bins={"1" : vsc.bin(1)})
                self.cp36 =vsc.coverpoint(lambda: ((uut.value >> 36) & 1), bins={"1" : vsc.bin(1)})
                self.cp37 =vsc.coverpoint(lambda: ((uut.value >> 37) & 1), bins={"1" : vsc.bin(1)})
                self.cp38 =vsc.coverpoint(lambda: ((uut.value >> 38) & 1), bins={"1" : vsc.bin(1)})
                self.cp39 =vsc.coverpoint(lambda: ((uut.value >> 39) & 1), bins={"1" : vsc.bin(1)})
                self.cp40 =vsc.coverpoint(lambda: ((uut.value >> 40) & 1), bins={"1" : vsc.bin(1)})
                self.cp41 =vsc.coverpoint(lambda: ((uut.value >> 41) & 1), bins={"1" : vsc.bin(1)})
                self.cp42 =vsc.coverpoint(lambda: ((uut.value >> 42) & 1), bins={"1" : vsc.bin(1)})
                self.cp43 =vsc.coverpoint(lambda: ((uut.value >> 43) & 1), bins={"1" : vsc.bin(1)})
                self.cp44 =vsc.coverpoint(lambda: ((uut.value >> 44) & 1), bins={"1" : vsc.bin(1)})
                self.cp45 =vsc.coverpoint(lambda: ((uut.value >> 45) & 1), bins={"1" : vsc.bin(1)})
                self.cp46 =vsc.coverpoint(lambda: ((uut.value >> 46) & 1), bins={"1" : vsc.bin(1)})
                self.cp47 =vsc.coverpoint(lambda: ((uut.value >> 47) & 1), bins={"1" : vsc.bin(1)})
                self.cp48 =vsc.coverpoint(lambda: ((uut.value >> 48) & 1), bins={"1" : vsc.bin(1)})
                self.cp49 =vsc.coverpoint(lambda: ((uut.value >> 49) & 1), bins={"1" : vsc.bin(1)})
                self.cp50 =vsc.coverpoint(lambda: ((uut.value >> 50) & 1), bins={"1" : vsc.bin(1)})
                self.cp51 =vsc.coverpoint(lambda: ((uut.value >> 51) & 1), bins={"1" : vsc.bin(1)})
                self.cp52 =vsc.coverpoint(lambda: ((uut.value >> 52) & 1), bins={"1" : vsc.bin(1)})
                self.cp53 =vsc.coverpoint(lambda: ((uut.value >> 53) & 1), bins={"1" : vsc.bin(1)})
                self.cp54 =vsc.coverpoint(lambda: ((uut.value >> 54) & 1), bins={"1" : vsc.bin(1)})
                self.cp55 =vsc.coverpoint(lambda: ((uut.value >> 55) & 1), bins={"1" : vsc.bin(1)})
                self.cp56 =vsc.coverpoint(lambda: ((uut.value >> 56) & 1), bins={"1" : vsc.bin(1)})
                self.cp57 =vsc.coverpoint(lambda: ((uut.value >> 57) & 1), bins={"1" : vsc.bin(1)})
                self.cp58 =vsc.coverpoint(lambda: ((uut.value >> 58) & 1), bins={"1" : vsc.bin(1)})
                self.cp59 =vsc.coverpoint(lambda: ((uut.value >> 59) & 1), bins={"1" : vsc.bin(1)})
                self.cp60 =vsc.coverpoint(lambda: ((uut.value >> 60) & 1), bins={"1" : vsc.bin(1)})
                self.cp61 =vsc.coverpoint(lambda: ((uut.value >> 61) & 1), bins={"1" : vsc.bin(1)})
                self.cp62 =vsc.coverpoint(lambda: ((uut.value >> 62) & 1), bins={"1" : vsc.bin(1)})
                self.cp63 =vsc.coverpoint(lambda: ((uut.value >> 63) & 1), bins={"1" : vsc.bin(1)})

        uut_i = uut()
        cg = internal_coverage(uut_i)
        cg_split = internal_coverage_split_cp(uut_i)

        count_wc = 1000
        start_wc_ms = int(round(time.time() * 1000))
        for i in range(count_wc):
            cg.sample()
        end_wc_ms = int(round(time.time() * 1000))

        count_split = 1000
        start_split_ms = int(round(time.time() * 1000))
        for i in range(count_split):
            cg_split.sample()
        end_split_ms = int(round(time.time() * 1000))

        print("Sample wildcard bins %d times in %dmS" % (count_wc, (end_wc_ms-start_wc_ms)))
        print("Sample split bins %d times in %dmS" % (count_split, (end_split_ms-start_split_ms)))

        # With caching, we expect sampling individual coverpoints to
        # take longer than sampling multiple bins
        self.assertGreater(
            (end_split_ms-start_split_ms),
            (end_wc_ms-start_wc_ms)
        )



        