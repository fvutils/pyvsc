'''
Created on Jun 21, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestListScalar(VscTestCase):
    
    def test_randsz_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint8_t())
                
            @vsc.constraint
            def l_c(self):
                self.l.size in vsc.rangelist(vsc.rng(1,10))
                
#                 with vsc.foreach(self.l, idx=True) as (idx,it):
#                     with vsc.if_then(idx > 0):
#                         self.l[idx] == self.l[idx-1]+1
                
        it = my_item_c()
        
        it.randomize()
        
        print("it.l.size=" + str(it.l.size))
        
        for i,v in enumerate(it.l):
            print("v[" + str(i) + "] = " + str(v))
