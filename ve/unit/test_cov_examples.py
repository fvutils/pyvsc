'''
Created on Jan 28, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase
import vsc
from vsc import report_coverage

class TestCovExamples(VscTestCase):
    
    def test_cov_1(self):

        @vsc.randobj
        class my_item_c(object):

            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a <= self.b
                self.b in vsc.rangelist(1,2,4,8)

        @vsc.covergroup
        class my_cg(object):

            def __init__(self):
                # Define the parameters accepted by the sample function
                self.with_sample({
                    'it' : my_item_c()
                })

                self.a_cp = vsc.coverpoint( self.it.a, bins={
                    # Create 4 bins across the space 0..255
                    'a_bins': vsc.bin_array([4], [0,255])
                })

                self.b_cp = vsc.coverpoint(self.it.b, bins={
                    # Create one bin for each value (1,2,4,8)
                    'b_bins': vsc.bin_array([], 1, 2, 4, 8)
                })
       

                self.ab_cross = vsc.cross([self.a_cp, self.b_cp])          


        it = my_item_c()
        it.a = 4
        it.b = 1
        
        my_cg_i = my_cg()
        
        my_cg_i.sample(it)
        it.b = 2
        my_cg_i.sample(it)
 
        report_coverage(details=True)
        print("coverage: %f %f" % (my_cg_i.a_cp.get_coverage(), my_cg_i.b_cp.get_coverage()))
        
    def test_cov_2(self):

        @vsc.randobj
        class my_item_c(object):

            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a <= self.b
                self.b in vsc.rangelist(1,2,4,8)

        @vsc.covergroup
        class my_cg(object):

            def __init__(self):
                # Define the parameters accepted by the sample function
                self.with_sample({
                    'a' : vsc.bit_t(8),
                    'b' : vsc.bit_t(8)
                })

                self.a_cp = vsc.coverpoint( self.a, bins={
                    # Create 4 bins across the space 0..255
                    'a_bins': vsc.bin_array([4], [0,255])
                })

                self.b_cp = vsc.coverpoint(self.b, bins={
                    # Create one bin for each value (1,2,4,8)
                    'b_bins': vsc.bin_array([], 1, 2, 4, 8)
                })
       
                self.ab_cross = vsc.cross([self.a_cp, self.b_cp])          


        it = my_item_c()
        it.a = 4
        it.b = 1
        
        my_cg_i = my_cg()
        
        my_cg_i.sample(it.a, it.b)
        it.b = 2
        my_cg_i.sample(it.a, it.b)

        self.assertEqual(my_cg_i.a_cp.get_coverage(), 25.0)
        self.assertEqual(my_cg_i.b_cp.get_coverage(), 50.0)
        self.assertEqual(my_cg_i.ab_cross.get_coverage(), 12.5)
        report_coverage(details=True)
        print("coverage: %f %f" % (my_cg_i.a_cp.get_coverage(), my_cg_i.b_cp.get_coverage()))
        
