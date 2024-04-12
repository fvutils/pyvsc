'''
Created on Jun 20, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter

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
        
        print("Model: " + ModelPrettyPrinter.print(c.get_model()))

        for i in range(100):        
            c.randomize()

            self.assertEqual(10, len(c.l))
            for i,it in enumerate(c.l):
                if i%2 == 0:
                    self.assertLess(it.a, it.b)
                else:
                    self.assertGreater(it.a, it.b)

    def test_heterogenous_content(self):
        @vsc.randobj
        class base_constraints_class(object):
            pass


        @vsc.randobj
        class base_rand_class(object):
            def __init__(self, name):
                self.name = name
                self.constraints = vsc.rand_list_t(base_constraints_class(), 0)

            def add_constraints(self, c):
                self.constraints.append(c)

    
        @vsc.randobj
        class user_constraints_class(base_constraints_class):
            def __init__(self, ptr):
                self.ptr = vsc.rand_attr(ptr)
#                self.ptr = ptr
#                self.ptr = vsc.rand_attr(user_rand_class("user_1"))
                pass

            @vsc.constraint
            def my_ptr_c(self):
                self.ptr.a == 8
                self.ptr.b == 1999


        @vsc.randobj
        class user_rand_class(base_rand_class):
            def __init__(self, name):
                super().__init__(name)
                self.a = vsc.rand_bit_t(16)
                self.b = vsc.rand_bit_t(16)


            @vsc.constraint
            def ab_c(self):
                self.a in vsc.rangelist(vsc.rng(1,1000))
                self.b in vsc.rangelist(vsc.rng(1000,2000))
                pass

            def print_fields(self):
                print(f"{self.name}: a={self.a}, b={self.b}")


        usr1 = user_rand_class("user_1")
        c = user_constraints_class(usr1)
        usr1.add_constraints(c)
        usr1.randomize(debug=0, solve_fail_debug=0)
        print("--------------------\n")
        usr1.print_fields()