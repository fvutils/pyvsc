'''
Created on Jan 28, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase
import vsc

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


        my_cg_i = my_cg()        
   
