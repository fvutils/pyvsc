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

    def test_obj_array(self):
        @vsc.randobj
        class MyRandObject:
            def __init__(self):
                self.a =vsc.rand_bit_t(4)

        @vsc.randobj
        class TopRandObj:
            def __init__(self):
                self.a = vsc.randsz_list_t(MyRandObject())
                
                for i in range(5):
                    self.a.append(MyRandObject())

            @vsc.constraint
            def a_c(self):
                self.a.size < 5
                self.a.size > 1

        my_top_rand = TopRandObj()
        my_top_rand.randomize(solve_fail_debug=1)
        self.assertGreater(my_top_rand.a.size, 1)
        self.assertLess(my_top_rand.a.size, 5)
        print("Size: %d" % my_top_rand.a.size)

