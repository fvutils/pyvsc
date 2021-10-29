'''
Created on May 3, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase

import vsc

class TestRandszArray(VscTestCase):
    
    def test_elems_match_size(self):
        
        @vsc.randobj
        class cls(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint16_t())
                
            @vsc.constraint
            def size_c(self):
                self.l.size.inside(vsc.rangelist(0,1,2,4,8,16))
                
            @vsc.constraint
            def val_c(self):
                with vsc.foreach(self.l, idx=True) as idx:
                    self.l[idx] == idx
                
        c = cls()
        
        with c.randomize_with() as it:
            it.l.size > 0
        self.assertIn(c.l.size, [1,2,4,8,16])

        print("size: %d" % c.l.size)        
        for i in range(c.l.size):
            self.assertEqual(c.l[i], i)

