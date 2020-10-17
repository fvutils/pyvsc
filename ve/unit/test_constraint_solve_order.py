'''
Created on Aug 20, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc.model.rand_info_builder import RandInfoBuilder
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter

class TestConstraintSolveOrder(VscTestCase):
    
    def test_depth_insufficient(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                vsc.solve_order(self.a, self.b)


        caught_exception = False
        try:
            i = my_c()
        except Exception:
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order outside constraint")
                
    def test_depth_excessive(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.b == 10
                    vsc.solve_order(self.a, self.b)                

        caught_exception = False
        try:
            i = my_c()
        except Exception:
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order buried in a constraint")
        
    def test_incorrect_args(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(1, self.b)
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        caught_exception = False
        try:
            i = my_c()
        except Exception as e:
            print("Exception: " + str(e))
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order incorrect arguments")

    def test_order_model_1(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)
                self.a < self.b
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        i = my_c()
        
#        i.randomize()
        model = i.get_model()
        model.set_used_rand(True)
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 2)
        a = model.find_field("a")
        b = model.find_field("b")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIn(a, info.randset_l[0].fields())
        self.assertIn(b, info.randset_l[1].fields())

    def test_order_model_2(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.b, self.c)
                vsc.solve_order(self.a, self.b)

                self.b < 30                
                self.a < 20
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        i = my_c()
        
#        i.randomize()
        model = i.get_model()
        model.set_used_rand(True)
        info = RandInfoBuilder.build([model], [])
        
        self.assertEqual(len(info.randset_l), 3)
        a = model.find_field("a")
        b = model.find_field("b")
        c = model.find_field("c")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNotNone(c)
        self.assertIn(a, info.randset_l[0].fields())
        self.assertIn(b, info.randset_l[1].fields())
        self.assertIn(c, info.randset_l[2].fields())
        
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.randset_l[1].constraints()), 2)
        self.assertEqual(len(info.randset_l[2].constraints()), 0)

    def test_order_hist_1(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)

                with vsc.if_then(self.a == 0):
                    self.b == 4
                with vsc.else_then:
                    self.b != 4
                    

        i = my_c()
        
        a_hist = [0]*2
        b_hist = [0]*2

        for x in range(100):
            i.randomize()
            a_hist[i.a] += 1
#            print("i.a=" + str(i.a) + " i.b=" + str(i.b))
            b_hist[0 if i.b == 4 else 1] += 1
            
        print("a_hist: " + str(a_hist))
        print("b_hist: " + str(b_hist))

