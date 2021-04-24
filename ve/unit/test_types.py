'''
Created on Apr 24, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestTypes(VscTestCase):
    
    def test_signed(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.rand_int_t(32), 3)  # intentionally using rand_int_t because I want signed

            @vsc.constraint
            def cx(self):
                with vsc.foreach(self.x, idx=True) as i:
                    self.x[i] >= -32768
                    self.x[i] <= 32768
                    
                    self.x[i] == i-27

        c = cl()
        c.randomize()
        for ii,i in enumerate(c.x):
            print(i)
            self.assertEquals(i, ii-27)
            