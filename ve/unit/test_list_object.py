'''
Created on Jun 20, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestListObject(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()

        @vsc.randobj                
        class container_c(object):
            
            def __init__(self):
                self.l = vsc.rand_list_t(item_c())
                
                for i in range(10):
                    self.l.append(item_c())

        c = container_c()
        c.randomize()
        
        for i,it in enumerate(c.l):
            print("Item[" + str(i) + "] a=" + str(it.a) + " b=" + str(it.b))
        
    def test_constraints(self):
        
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()

        @vsc.randobj                
        class container_c(object):
            
            def __init__(self):
                self.l = vsc.rand_list_t(item_c())
                
                for i in range(10):
                    self.l.append(item_c())
                    
            @vsc.constraint
            def all_eq_c(self):
                with vsc.foreach(self.l) as it:
                    it.a == it.b

        c = container_c()

        for i in range(100):        
            c.randomize()
            
            for it in c.l:
                self.assertEqual(it.a, it.b)
            
                    