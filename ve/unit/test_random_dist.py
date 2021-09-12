'''
Created on Jun 1, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestRandomDist(VscTestCase):
    
    def test_histogram(self):
        @vsc.randobj
        class fifo_driver_random(object):
        
            def __init__(self):
        
                self.L = 8
        
                # random, unsigned (bit), and L-bits wide
        
                self.rand_bit_1 = vsc.rand_bit_t(self.L)
                self.rand_bit_1_hist = [0 for i in range(2**self.L)]
        
                self.rand_bit_2 = vsc.rand_bit_t(self.L)
                self.rand_bit_2_hist = [0 for i in range(2**self.L)]
        
                self.rand_bit_3 = vsc.rand_bit_t(self.L)
                self.rand_bit_3_hist = [0 for i in range(2**self.L)]
        
                self.rand_bit_4 = vsc.rand_bit_t(self.L)
                self.rand_bit_4_hist = [0 for i in range(2**self.L)]
        
            @vsc.constraint
            def get_random_ch(self):
        
                self.rand_bit_1 < 10
                self.rand_bit_2 < 30
                self.rand_bit_3 < 100
                self.rand_bit_4 < 200

        rand_obj = fifo_driver_random()
        NbLoops = 1000

        for i in range(NbLoops):

            rand_obj.randomize()

            # random, unsigned (bit), and L-bits wide
            self.assertLess(rand_obj.rand_bit_1, 10)
            self.assertLess(rand_obj.rand_bit_2, 30)
            self.assertLess(rand_obj.rand_bit_3, 100)
            self.assertLess(rand_obj.rand_bit_4, 200)
            rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] = rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] + 1
            rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] = rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] + 1
            rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] = rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] + 1
            rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] = rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] + 1

        print("\n\nself.rand_bit_1 histogram is:", rand_obj.rand_bit_1_hist[0:9])
        print("\n\nself.rand_bit_2 histogram is:", rand_obj.rand_bit_2_hist[0:29])
        print("\n\nself.rand_bit_3 histogram is:", rand_obj.rand_bit_3_hist[0:99])
        print("\n\nself.rand_bit_4 histogram is:", rand_obj.rand_bit_4_hist[0:199])
        
#     def test_histogram_lt(self):
#         @vsc.randobj
#         class fifo_driver_random(object):
#         
#             def __init__(self):
#         
#                 self.L = 8
#         
#                 # random, unsigned (bit), and L-bits wide
#         
#                 self.rand_bit_1 = vsc.rand_bit_t(self.L)
#                 self.rand_bit_1_hist = [0 for i in range(2**self.L)]
#         
#                 self.rand_bit_2 = vsc.rand_bit_t(self.L)
#                 self.rand_bit_2_hist = [0 for i in range(2**self.L)]
#         
#                 self.rand_bit_3 = vsc.rand_bit_t(self.L)
#                 self.rand_bit_3_hist = [0 for i in range(2**self.L)]
#         
#                 self.rand_bit_4 = vsc.rand_bit_t(self.L)
#                 self.rand_bit_4_hist = [0 for i in range(2**self.L)]
#         
#             @vsc.constraint
#             def get_random_ch(self):
#         
#                 self.rand_bit_1 < 10
#                 self.rand_bit_2 < 30
#                 self.rand_bit_3 < 100
#                 
#                 self.rand_bit_1 < self.rand_bit_2
# 
#         rand_obj = fifo_driver_random()
#         NbLoops = 3000
# 
#         for i in range(NbLoops):
# 
#             rand_obj.randomize()
# 
#             # random, unsigned (bit), and L-bits wide
#             self.assertLess(rand_obj.rand_bit_1, 10)
#             self.assertLess(rand_obj.rand_bit_2, 30)
#             self.assertLess(rand_obj.rand_bit_3, 100)
#             rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] = rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] + 1
#             rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] = rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] + 1
#             rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] = rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] + 1
#             rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] = rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] + 1
# 
#         print("\n\nself.rand_bit_1 histogram is:", rand_obj.rand_bit_1_hist[0:9])
#         print("\n\nself.rand_bit_2 histogram is:", rand_obj.rand_bit_2_hist[1:29])
#         print("\n\nself.rand_bit_3 histogram is:", rand_obj.rand_bit_3_hist[0:99])
#         print("\n\nself.rand_bit_4 histogram is:", rand_obj.rand_bit_4_hist)
#         
#         z_cnt=0
#         for v in rand_obj.rand_bit_1_hist[0:9]:
#             if v == 0:
#                 z_cnt += 1
#         self.assertEqual(z_cnt, 0)
#         z_cnt=0
#         for v in rand_obj.rand_bit_2_hist[1:29]:
#             if v == 0:
#                 z_cnt += 1
#         self.assertEqual(z_cnt, 0)
#         z_cnt=0
#         for v in rand_obj.rand_bit_3_hist[0:99]:
#             if v == 0:
#                 z_cnt += 1
#         self.assertEqual(z_cnt, 0)
#         z_cnt=0
#         for v in rand_obj.rand_bit_4_hist:
#             if v == 0:
#                 z_cnt += 1
#         # Know that it's likely to take ~2560 to hit all
#         self.assertLess(z_cnt, 8)
#         self.assertEqual(z_cnt, 0)

    def test_dist_nre_lt(self):
        @vsc.randobj
        class cls(object):
        
            def __init__(self):
                self.v1 = vsc.rand_bit_t(8)
                self.v2 = vsc.rand_bit_t(8)
        
            @vsc.constraint
            def get_random_ch(self):
                self.v1 < 16
                self.v2 < 32
        
        obj = cls()
        n_iter = 64*10
        
        hist_v1 = [0]*255
        hist_v2 = [0]*255

        for i in range(n_iter):
            obj.randomize()
            
            hist_v1[obj.v1] += 1
            hist_v2[obj.v2] += 1

        print("hist_v1: " + str(hist_v1))
        print("hist_v2: " + str(hist_v2))

        # Check all values
        for i in range(255):
            if i < 16:
                self.assertNotEqual(hist_v1[i], 0)
            else:
                self.assertEquals(hist_v1[i], 0)
                
        for i in range(255):
            if i < 32:
                self.assertNotEqual(hist_v2[i], 0)
            else:
                self.assertEquals(hist_v2[i], 0)

    def test_dist_nre_le(self):
        @vsc.randobj
        class cls(object):
        
            def __init__(self):
                self.v1 = vsc.rand_bit_t(8)
                self.v2 = vsc.rand_bit_t(8)
        
            @vsc.constraint
            def get_random_ch(self):
                self.v1 <= 15
                self.v2 <= 31
        
        obj = cls()
        n_iter = 64*10
        
        hist_v1 = [0]*255
        hist_v2 = [0]*255

        for i in range(n_iter):
            obj.randomize()
            
            hist_v1[obj.v1] += 1
            hist_v2[obj.v2] += 1

        print("hist_v1: " + str(hist_v1))
        print("hist_v2: " + str(hist_v2))

        # Check all values
        for i in range(255):
            if i < 16:
                self.assertNotEqual(hist_v1[i], 0)
            else:
                self.assertEquals(hist_v1[i], 0)
                
        for i in range(255):
            if i < 32:
                self.assertNotEqual(hist_v2[i], 0)
            else:
                self.assertEquals(hist_v2[i], 0)
                
    def test_dist_var_lt(self):
        @vsc.randobj
        class cls(object):
        
            def __init__(self):
                self.v1 = vsc.rand_bit_t(8)
                self.v1_b = vsc.rand_bit_t(8)
                self.v2 = vsc.rand_bit_t(8)
                self.v2_b = vsc.rand_bit_t(8)
        
            @vsc.constraint
            def get_random_ch(self):
                self.v1_b == 16
                self.v2_b == 32
                self.v1 < self.v1_b
                self.v2 < self.v2_b
        
        obj = cls()
        n_iter = 64*10
        
        hist_v1 = [0]*255
        hist_v2 = [0]*255

        for i in range(n_iter):
            obj.randomize()
            
            hist_v1[obj.v1] += 1
            hist_v2[obj.v2] += 1

        print("hist_v1: " + str(hist_v1))
        print("hist_v2: " + str(hist_v2))

        # Check all values
        for i in range(255):
            if i < 16:
                self.assertNotEqual(hist_v1[i], 0)
            else:
                self.assertEquals(hist_v1[i], 0)
                
        for i in range(255):
            if i < 32:
                self.assertNotEqual(hist_v2[i], 0)
            else:
                self.assertEquals(hist_v2[i], 0)                

    def test_dist_var_lte(self):
        @vsc.randobj
        class cls(object):
        
            def __init__(self):
                self.v1 = vsc.rand_bit_t(8)
                self.v1_b = vsc.rand_bit_t(8)
                self.v2 = vsc.rand_bit_t(8)
                self.v2_b = vsc.rand_bit_t(8)
        
            @vsc.constraint
            def get_random_ch(self):
                self.v1_b == 15
                self.v2_b == 31
                self.v1 <= self.v1_b
                self.v2 <= self.v2_b
        
        obj = cls()
        n_iter = 64*20
        
        hist_v1 = [0]*255
        hist_v2 = [0]*255

        for i in range(n_iter):
            obj.randomize()
            
            hist_v1[obj.v1] += 1
            hist_v2[obj.v2] += 1

        print("hist_v1: " + str(hist_v1))
        print("hist_v2: " + str(hist_v2))

        # Check all values
        for i in range(255):
            if i < 16:
                self.assertNotEqual(hist_v1[i], 0)
            else:
                self.assertEquals(hist_v1[i], 0)
                
        for i in range(255):
            if i < 32:
                self.assertNotEqual(hist_v2[i], 0)
            else:
                self.assertEquals(hist_v2[i], 0)                                                
                
                
    def test_dist_nre_listsz_lt(self):
        @vsc.randobj
        class cls(object):
        
            def __init__(self):
                self.v1 = vsc.randsz_list_t(vsc.rand_bit_t(8))
                self.v2 = vsc.randsz_list_t(vsc.rand_bit_t(8))
        
            @vsc.constraint
            def get_random_ch(self):
                self.v1.size < 16
                self.v2.size < 32
        
        obj = cls()
        n_iter = 64*20
        
        hist_v1 = [0]*255
        hist_v2 = [0]*255

        for i in range(n_iter):
            obj.randomize()
            
            hist_v1[obj.v1.size] += 1
            hist_v2[obj.v2.size] += 1

        print("hist_v1: " + str(hist_v1))
        print("hist_v2: " + str(hist_v2))

        # Check all values
        for i in range(255):
            if i < 16:
                self.assertNotEqual(hist_v1[i], 0)
            else:
                self.assertEquals(hist_v1[i], 0)
                
        for i in range(255):
            if i < 32:
                self.assertNotEqual(hist_v2[i], 0)
            else:
                self.assertEquals(hist_v2[i], 0)                                     

    def test_xy_constraint_dist(self):
        
        @vsc.randobj
        class cls(object):
            
            def __init__(self):
                self.x = vsc.rand_bit_t(3)
                self.y = vsc.rand_bit_t(3)
                
            @vsc.constraint
            def x_lt_y_c(self):
                self.x < self.y
                
            
        x_hist = [0]*8
        y_hist = [0]*8

        c = cls()        
        for i in range(10000):
            c.randomize(debug=0)
            x_hist[c.x] += 1
            y_hist[c.y] += 1

        print("x_hist=" + str(x_hist))
        print("y_hist=" + str(y_hist))
        
    def test_compound_arrays(self):
        import vsc 
#        import matplotlib.pyplot as plt
        
        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(10):    
                    self.c1.append(vsc.attr(Child1()))
        
                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(10):
                    self.c2.append(vsc.attr(Child2()))
        
                self.non_list_child = vsc.rand_attr(Child1())
        
                self.top_lvl_val = vsc.rand_uint8_t(0)
            
            @vsc.constraint
            def parent_c(self):
                self.top_lvl_val < 10       # Works fine
        
                # Presence of list causes high skewness
                self.c1[0].one_lvl_below_val < 10
                self.c1[0].a[0].value < 10      # Two levels below
        
                self.non_list_child.one_lvl_below_val < 10      # Works fine
                
        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)
        
        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(5):    
                    self.a.append(vsc.attr(Field('a', 10)))
        
                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(5):    
                    self.b.append(vsc.attr(Field('b', 10)))
        
                self.one_lvl_below_val = vsc.rand_uint8_t(0)
            
        
        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.attr(Field('x', 10)))
                for i in range(5):    
                    self.x.append(vsc.attr(Field('x', 10)))
        
                self.y = vsc.rand_list_t(vsc.attr(Field('y', 10)))
                for i in range(5):    
                    self.y.append(vsc.attr(Field('y', 10)))
            
            @vsc.constraint
            def test_c(self):
                self.x[0].value < self.x[1].value
        
        inst=Parent()
        
        top_lvl = []
        top_lvl_hist = [0]*10
        one_below = []
        one_below_hist = [0]*10
        two_below = []
        two_below_hist = [0]*10
        non_list = []
        non_list_hist = [0]*10
        
        for i in range(1000):
            inst.randomize(debug=0)
            top_lvl.append(inst.top_lvl_val)
            top_lvl_hist[inst.top_lvl_val%10] += 1
            one_below.append(inst.c1[0].one_lvl_below_val)
            one_below_hist[inst.c1[0].one_lvl_below_val%10] += 1
            two_below.append(inst.c1[0].a[0].value)
            two_below_hist[inst.c1[0].a[0].value%10] += 1
            non_list.append(inst.non_list_child.one_lvl_below_val)
            non_list_hist[inst.non_list_child.one_lvl_below_val%10] += 1
        
#        plt.hist(top_lvl)
#        plt.title("Top level variable values")
#        plt.show()
        print("top_lvl_hist: " + str(top_lvl_hist))
        zeros = 0
        for e in top_lvl_hist:
            if e == 0:
                zeros += 1
        self.assertEqual(zeros, 0)
        
#        plt.hist(one_below)
#        plt.title("Variables one level below (with list)")
#        plt.show()
        print("one_below: " + str(one_below_hist))
        zeros = 0
        for e in one_below_hist:
            if e == 0:
                zeros += 1
        self.assertEqual(zeros, 0)
        
#        plt.hist(two_below)
#        plt.title("Variables two levels below (with lists)")
#        plt.show()
        print("two_below: " + str(two_below_hist))
        zeros = 0
        for e in two_below_hist:
            if e == 0:
                zeros += 1
        self.assertEqual(zeros, 0)
        
#        plt.hist(non_list)
#        plt.title("Child not in list")
#        plt.show()
        print("non_list: " + str(non_list_hist))
        zeros = 0
        for e in non_list_hist:
            if e == 0:
                zeros += 1
        self.assertEqual(zeros, 0)
        
    def test_if_then_dist(self):
        import vsc
        
        @vsc.randobj
        class BranchInstr:
            def __init__(self):
                self.type = vsc.rand_bit_t(1)
                self.disp = vsc.rand_bit_t(22)
        
            @vsc.constraint
            def short_offset_cnstr(self):
                with vsc.if_then(self.type == 0):
                    self.disp <= 4096
                with vsc.else_then:
                    self.disp <= 4096
        
            def __str__(self):
                return(f"type = {self.type}, displacement = {self.disp}")
            
        branchInstr = BranchInstr()
        for i in range(32):
            branchInstr.randomize()
            print(branchInstr)        
            
    def test_partsel_dist_stuck_at(self):
        import vsc
        
        @vsc.randobj
        class my_d:
        
            def __init__(self):
                self.value = vsc.rand_bit_t(4)
                self.a = vsc.rand_bit_t(1)
                self.b = vsc.rand_bit_t(1)
        
            @vsc.constraint
            def a_c1(self):
                vsc.solve_order(self.a, self.value)
                vsc.solve_order(self.b, self.value)
        
            @vsc.constraint
            def a_c2(self):
                self.value[3] == self.a
                self.value[2] == self.b

        hist = [0]*4
        td = my_d()
        for i in range(100):
            with td.randomize_with() as it:
                it.a == 1
                it.b == 0

            hist[td.value & 0x3] += 1        
#            print("a = " + str(td.a) + "  b = " + str(td.b) + "  value = " + str(hex(td.value)))        
        
        print("hist: %s" % str(hist))
        
        for i,v in enumerate(hist):
            self.assertNotEqual(v, 0)

    def test_partsel_dist(self):
        import vsc
        
        @vsc.randobj
        class my_d:
        
            def __init__(self):
                self.value = vsc.rand_bit_t(4)
                self.a = vsc.rand_bit_t(1)
                self.b = vsc.rand_bit_t(1)
        
            @vsc.constraint
            def a_c1(self):
                vsc.solve_order(self.a, self.value)
                vsc.solve_order(self.b, self.value)
        
            @vsc.constraint
            def a_c2(self):
                self.value[3] == self.a
                self.value[2] == self.b

        hist_a = [0]*2
        hist_b = [0]*2
        hist = [0]*16
        
        td = my_d()
        for i in range(480):
            with td.randomize_with() as it:
                pass

            hist_a[td.a] += 1
            hist_b[td.b] += 1
            hist[td.value] += 1
#            print("a = " + str(td.a) + "  b = " + str(td.b) + "  value = " + str(hex(td.value)))        
        
        print("hist: value=%s a=%s b=%s" % (str(hist), str(hist_a), str(hist_b)))
        
        for i,v in enumerate(hist):
            self.assertNotEqual(v, 0)        

        