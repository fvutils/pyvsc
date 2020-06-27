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

    def test_init_array_block(self):
        
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
                with vsc.foreach(self.l, it=True,idx=True) as (idx,it):
                    with vsc.if_then((idx&1) == 0):
                        it.a < it.b
                    with vsc.else_then:
                        it.a > it.b

        c = container_c()

        for i in range(100):        
            c.randomize()

            self.assertEqual(10, len(c.l))
            for i,it in enumerate(c.l):
                if (i%2) == 0:
                    self.assertLess(it.a, it.b)
                else:
                    self.assertGreater(it.a, it.b)

    def test_diff_classes(self):
        
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        @vsc.randobj
        class item_c_1(item_c):
            def __init__(self):
                super().__init__()
                
            @vsc.constraint
            def a_lt_b_c(self):
                self.a < self.b
                
        @vsc.randobj
        class item_c_2(item_c):
            def __init__(self):
                super().__init__()
                
            @vsc.constraint
            def a_gt_b_c(self):
                self.a > self.b

        @vsc.randobj                
        class container_c(object):
            
            def __init__(self):
                self.l = vsc.rand_list_t(item_c())

                for i in range(10):
                    if i%2 == 0:
                        self.l.append(item_c_1())
                    else:
                        self.l.append(item_c_2())
                                                        
        c = container_c()

        for i in range(100):        
            c.randomize()

            self.assertEqual(10, len(c.l))
            for i,it in enumerate(c.l):
                if i%2 == 0:
                    self.assertLess(it.a, it.b)
                else:
                    self.assertGreater(it.a, it.b)

