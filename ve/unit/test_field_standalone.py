'''
Created on Jul 30, 2020

@author: ballance
'''

import vsc
from vsc_test_case import VscTestCase

class TestFieldStandalone(VscTestCase):
    
    def test_simple_int(self):
        a = vsc.rand_uint8_t()
        
        print("a=" + str(a.get_val()))
        self.assertEqual(a.get_val(), 0);
        
    def test_simple_rand(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        vsc.randomize(a, b)
                
        print("a=" + str(a.get_val()) + " b=" + str(b.get_val()))
        
    def test_simple_rand_inline1(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a < b
            self.assertLess(a.get_val(), b.get_val())
            
    def test_simple_rand_inline2(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a < b
            self.assertLess(a.val, b.val)
                
        