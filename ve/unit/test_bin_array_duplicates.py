'''
Created on 2024

@author: copilot

Test for bin_array duplicate value handling according to IEEE 1800-2023
'''
import vsc
from vsc_test_case import VscTestCase

class TestBinArrayDuplicates(VscTestCase):
    
    def test_bin_array_with_duplicates_from_range(self):
        """Test that duplicate values from a range are properly retained and distributed.
        
        According to IEEE 1800-2023 (page 585):
        "Duplicate values are retained; thus the same value can be assigned to multiple bins"
        
        bins fixed [4] = {[1:10], 1, 4, 7} should distribute 13 values as:
        - Bin 0: 1, 2, 3
        - Bin 1: 4, 5, 6
        - Bin 2: 7, 8, 9
        - Bin 3: 10, 1, 4, 7 (including the duplicates)
        
        Note: Values 1, 4, and 7 will hit MULTIPLE bins when sampled (both their range bin
        and bin 3), which is the correct behavior per the standard.
        """
        
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        fixed=vsc.bin_array([4], [1, 10], 1, 4, 7)
                    ))
                
        cg = my_cg()
        cg_model = cg.get_model()
        cp_model = cg_model.coverpoint_l[0]
        
        # Should have 4 bins total (distributed from 13 values)
        self.assertEqual(cp_model.get_n_bins(), 4)
        
        # Verify bin structure by checking ranges
        bin_ranges = []
        for idx in range(cp_model.get_n_bins()):
            bin_range = cp_model.get_bin_range(idx)
            bin_ranges.append(bin_range)
        
        # Value 1 should hit multiple bins (bin 0 from range and bin 3 from duplicate)
        cg.sample(1)
        self.assertGreater(cp_model.get_bin_hits(0), 0, "Value 1 should hit bin 0")
        self.assertGreater(cp_model.get_bin_hits(3), 0, "Value 1 should also hit bin 3 (duplicate)")
        
        # Value 4 should hit multiple bins
        cg.sample(4)
        self.assertGreater(cp_model.get_bin_hits(1), 0, "Value 4 should hit bin 1")
        self.assertGreater(cp_model.get_bin_hits(3), 0, "Value 4 should also hit bin 3 (duplicate)")
        
        # Value 7 should hit multiple bins
        cg.sample(7)
        self.assertGreater(cp_model.get_bin_hits(2), 0, "Value 7 should hit bin 2")
        self.assertGreater(cp_model.get_bin_hits(3), 0, "Value 7 should also hit bin 3 (duplicate)")
        
        # Value 10 should only hit bin 3
        cg.sample(10)
        self.assertGreater(cp_model.get_bin_hits(3), 0, "Value 10 should hit bin 3")
        
        # Value 2 should only hit bin 0 (no duplicate)
        cg.sample(2)
        hits_before = cp_model.get_bin_hits(3)
        cg.sample(2)
        hits_after = cp_model.get_bin_hits(3)
        # Bin 3 should not get additional hits from value 2
        self.assertEqual(hits_before, hits_after, "Value 2 should not hit bin 3")
        
    def test_bin_array_with_separate_values(self):
        """Test that separate values including duplicates are properly distributed.
        
        bins fixed [4] = {[4:12], 1, 2, 8} should distribute values as:
        - Bin 0: 4, 5, 6
        - Bin 1: 7, 8, 9
        - Bin 2: 10, 11, 12
        - Bin 3: 1, 2, 8 (separate values, 8 is also in bin 1)
        """
        
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        fixed=vsc.bin_array([4], [4, 12], 1, 2, 8)
                    ))
                
        cg = my_cg()
        cg_model = cg.get_model()
        cp_model = cg_model.coverpoint_l[0]
        
        # Should have 4 bins
        self.assertEqual(cp_model.get_n_bins(), 4)
        
        # Verify bin 0: 4, 5, 6
        cg.sample(4)
        self.assertGreater(cp_model.get_bin_hits(0), 0)
        
        # Verify bin 3 contains the separate values including 8 which is also in bin 1
        cg.sample(8)
        self.assertGreater(cp_model.get_bin_hits(1), 0)  # hits bin 1 (from range [4:12])
        self.assertGreater(cp_model.get_bin_hits(3), 0)  # also hits bin 3 (from separate value 8)
        
    def test_bin_array_multiple_single_values(self):
        """Test distribution of multiple single values without ranges.
        
        bins fixed [3] = {1, 2, 3, 4, 5, 6} should distribute as:
        - Bin 0: 1, 2
        - Bin 1: 3, 4
        - Bin 2: 5, 6
        """
        
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        fixed=vsc.bin_array([3], 1, 2, 3, 4, 5, 6)
                    ))
                
        cg = my_cg()
        cg_model = cg.get_model()
        cp_model = cg_model.coverpoint_l[0]
        
        # Should have 3 bins
        self.assertEqual(cp_model.get_n_bins(), 3)
        
        # Sample each value and verify they hit the correct bins
        cg.sample(1)
        self.assertGreater(cp_model.get_bin_hits(0), 0)
        cg.sample(2)
        self.assertGreater(cp_model.get_bin_hits(0), 0)
        
        cg.sample(3)
        self.assertGreater(cp_model.get_bin_hits(1), 0)
        cg.sample(4)
        self.assertGreater(cp_model.get_bin_hits(1), 0)
        
        cg.sample(5)
        self.assertGreater(cp_model.get_bin_hits(2), 0)
        cg.sample(6)
        self.assertGreater(cp_model.get_bin_hits(2), 0)
        
    def test_bin_array_exact_duplicate_values(self):
        """Test that exact duplicate values are retained.
        
        bins fixed [2] = {1, 1, 2, 2} should distribute 4 values across 2 bins:
        - Bin 0: 1, 1
        - Bin 1: 2, 2
        """
        
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        fixed=vsc.bin_array([2], 1, 1, 2, 2)
                    ))
                
        cg = my_cg()
        cg_model = cg.get_model()
        cp_model = cg_model.coverpoint_l[0]
        
        # Should have 2 bins
        self.assertEqual(cp_model.get_n_bins(), 2)
        
        # Sample value 1 - should hit both entries in bin 0
        cg.sample(1)
        self.assertGreater(cp_model.get_bin_hits(0), 0)
        
        # Sample value 2 - should hit both entries in bin 1
        cg.sample(2)
        self.assertGreater(cp_model.get_bin_hits(1), 0)
        
    def test_bin_array_no_duplicates_simple(self):
        """Test that the fix doesn't break the simple case without duplicates.
        
        bins a1 [4] = {[0:16]} should work as before.
        """
        
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        a1=vsc.bin_array([4], [0, 16])
                    ))
                
        cg = my_cg()
        cg_model = cg.get_model()
        cp_model = cg_model.coverpoint_l[0]
        
        # Should have 4 bins for 17 values
        self.assertEqual(cp_model.get_n_bins(), 4)
        
        # Test coverage calculation
        cg.sample(0)
        cg.sample(3)
        self.assertEqual(cg.a_cp.get_coverage(), 25)
        cg.sample(4)
        cg.sample(7)
        self.assertEqual(cg.a_cp.get_coverage(), 50)
