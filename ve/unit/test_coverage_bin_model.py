'''
Created on Mar 20, 2020

@author: ballance
'''
from unittest.case import TestCase
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.rangelist_model import RangelistModel
from vsc.model.coverpoint_bin_single_range_model import CoverpointBinSingleRangeModel
from vsc.model.coverpoint_bin_single_bag_model import CoverpointBinSingleBagModel

class TestCoverageBinModel(TestCase):
    
    def test_partition_single_range_even(self):
        
        rangelist = RangelistModel([
                [1,16]
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())
        self.assertTrue(isinstance(bins.bin_l[3], CoverpointBinSingleRangeModel))
        self.assertEqual(16, bins.bin_l[3].target_val_high)
        
    def test_partition_single_range_odd(self):
        
        rangelist = RangelistModel([
                [1,18]
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())        
        self.assertTrue(isinstance(bins.bin_l[3], CoverpointBinSingleBagModel))
        self.assertEqual(18, bins.bin_l[3].binspec.range_l[-1][1])
        
    def test_partition_individual_consecutive_values(self):
        
        rangelist = RangelistModel([
                1, 2, 3, 4, 5, 6, 7, 8, 
                9, 10, 11, 12, 13, 14, 15, 16
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())
        for b in bins.bin_l:
            self.assertTrue(isinstance(b, CoverpointBinSingleBagModel))
            
    def test_partition_individual_nonconsecutive_values(self):
        rangelist = RangelistModel([
                1, 3, 5, 7, 9, 11, 13, 
                15, 17, 19, 21, 23, 25
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())
        for b in bins.bin_l:
            self.assertTrue(isinstance(b, CoverpointBinSingleBagModel))

    def test_partition_mixed_consecutive_values(self):
        rangelist = RangelistModel([
                1, 2, 3, [4,7], 8, 11, 13, 
                [9,13], 14, 15
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())

    def test_partition_mixed_nonconsecutive_values(self):
        rangelist = RangelistModel([
                1, 3, 5, [7,10], 12, 
                [13,15], 17, [19,22]
            ])
        
        bins = CoverpointBinCollectionModel.mk_collection(
            "bin", 
            rangelist, 
            4)

        bins.finalize(0)
        self.assertEqual(4, len(bins.bin_l))
        self.assertEqual(4, bins.get_n_bins())

    
