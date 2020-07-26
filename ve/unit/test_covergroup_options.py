'''
Created on Apr 11, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestCovergroupOptions(VscTestCase):
    
    def test_comment(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, a, b):
                
                self.a_cp = vsc.coverpoint(a, cp_t=vsc.uint8_t())
                self.b_cp = vsc.coverpoint(b, cp_t=vsc.uint8_t())

        a = 0
        b = 0                
        cg1 = my_cg(lambda:a, lambda:b)
        cg1.options.name = "my_cg1"
        cg1.options.comment = "cg1"