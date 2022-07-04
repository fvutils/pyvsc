'''
Created on Jun 28, 2022

@author: mballance
'''
import vsc2
from vsc_test_case2 import VscTestCase2

class TestListBasics(VscTestCase2):
    
    def test_smoke(self):
        
        @vsc2.randclass
        class cls(object):
            list_t = vsc2.list_t[vsc2.uint8_t]
            
            l1 : vsc2.rand[list_t]
            l2 : vsc2.rand_list_t[vsc2.uint8_t]
            
    def test_randobj_compat_smoke(self):
        
        @vsc2.randobj
        class cls(object):
            
            def __init__(self):
                self.l2 = vsc2.rand_list_t(vsc2.uint8_t, 10)
                
        o = cls()
        