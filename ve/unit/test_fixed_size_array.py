'''
Created on Mar 4, 2020

@author: ballance
'''

from unittest import TestCase
import vsc
from vsc_test_case import VscTestCase

class TestFixedSizeArray(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_arr = vsc.rand_list_t(vsc.uint8_t(), 16)
                
    