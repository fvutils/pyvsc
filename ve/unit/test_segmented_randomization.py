'''
Created on Mar 1, 2020

@author: ballance
'''
from unittest.case import TestCase
import vsc

class TestSegmentedRandomization(TestCase):
    
    def test_postrand_randomization(self):
        """
        Tests that we can successfully call 'randomize' on a field
        not initially declared 'rand'
        """
        
        
        
        @vsc.randobj
        class sub_item(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                
            @vsc.constraint
            def ab_c(self):
                self.a != self.b
                
        @vsc.randobj
        class item(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)
                self.c = vsc.attr(sub_item())
                
            @vsc.constraint
            def ab_c(self):
                self.a == self.c.a
                
            def post_randomize(self):
                old_a = self.c.a
                with self.c.randomize_with() as it:
                    it.a == (old_a+1)
                
        it = item()

        for i in range(16):
            it.randomize()
            self.assertEqual(it.a, i)
            self.assertNotEqual(it.c.a, it.c.b)
