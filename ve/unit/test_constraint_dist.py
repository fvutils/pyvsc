'''
Created on Aug 9, 2020

@author: ballance
'''

import vsc
from enum import Enum, auto, IntEnum

from .vsc_test_case import VscTestCase


class TestConstraintDist(VscTestCase):
    
    def test_dist_in_range(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(1, 10),
                    vsc.weight(2, 20),
                    vsc.weight(4, 40),
                    vsc.weight(8, 80)])
                
        c = my_c()

        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1,2,4,8])
            
    def test_dist_static_zero_weight(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(1, 10),
                    vsc.weight(2, 0),
                    vsc.weight(4, 40),
                    vsc.weight(8, 80)])
                
        c = my_c()

        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1,4,8])

    def test_dist_dynamic_zero_weight(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.en_one = vsc.uint8_t()
                self.en_two = vsc.uint8_t()
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(1, self.en_one),
                    vsc.weight(2, self.en_two),])
                
        c = my_c()

        c.en_one = 1
        c.en_two = 0
        for i in range(10):
            c.randomize()
            self.assertEqual(c.a, 1)            
        c.en_one = 0
        c.en_two = 1
        for i in range(10):
            c.randomize()
            self.assertEqual(c.a, 2)
        c.en_one = 1
        c.en_two = 1
        for i in range(10):
            c.randomize()
            self.assertIn(c.a, [1,2])

    def test_dist_static_weights(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(1, 80),
                    vsc.weight(2, 40),
                    vsc.weight(3, 20),
                    vsc.weight(4, 10)])
                
        c = my_c()
        
        hist = 4*[0]

        for i in range(100):
            c.randomize()
            self.assertIn(c.a, [1,2,3,4])
            print("a=" + str(c.a))
            hist[c.a-1] += 1

        print("hist: " + str(hist))

    def test_dist_static_weight_ranges(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight((10,15),  80),
                    vsc.weight((20,30),  40),
                    vsc.weight((40,70),  20),
                    vsc.weight((80,100), 10)])
                
        c = my_c()
        
        hist = 4*[0]

        for i in range(100):
            c.randomize()
            print("a=" + str(c.a))
            if c.a >= 10 and c.a <= 15:
                hist[0] += 1
            elif c.a >= 20 and c.a <= 30:
                hist[1] += 1
            elif c.a >= 40 and c.a <= 70:
                hist[2] += 1
            elif c.a >= 80 and c.a <= 100:
                hist[3] += 1
            else:
                self.fail("Value " + str(c.a) + " illegal")

        print("hist: " + str(hist))

    def test_dist_conditional_weights(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.uint8_t()
                
            @vsc.constraint
            def dist_a(self):
                with vsc.if_then(self.b == 1):
                    vsc.dist(self.a, [
                        vsc.weight((10,15),  80),
                        vsc.weight((20,30),  40),
                        vsc.weight((40,70),  20),
                        vsc.weight((80,100), 10)])
                with vsc.else_then:
                    vsc.dist(self.a, [
                        vsc.weight((10,15),  10),
                        vsc.weight((20,30),  20),
                        vsc.weight((40,70),  40),
                        vsc.weight((80,100), 80)])
                
        c = my_c()
        
        hist = 4*[0]
        c.b = 1
        for i in range(100):
            c.randomize()
            if c.a >= 10 and c.a <= 15:
                hist[0] += 1
            elif c.a >= 20 and c.a <= 30:
                hist[1] += 1
            elif c.a >= 40 and c.a <= 70:
                hist[2] += 1
            elif c.a >= 80 and c.a <= 100:
                hist[3] += 1
            else:
                self.fail("Value " + str(c.a) + " illegal")
        print("hist: " + str(hist))
        
        hist = 4*[0]
        c.b = 0
        for i in range(100):
            c.randomize()
            if c.a >= 10 and c.a <= 15:
                hist[0] += 1
            elif c.a >= 20 and c.a <= 30:
                hist[1] += 1
            elif c.a >= 40 and c.a <= 70:
                hist[2] += 1
            elif c.a >= 80 and c.a <= 100:
                hist[3] += 1
            else:
                self.fail("Value " + str(c.a) + " illegal")
        print("hist: " + str(hist))        
        
    def test_dist_conditional_weights_rand(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_bit_t(1)
                
            @vsc.constraint
            def dist_a(self):
                with vsc.if_then(self.b == 1):
                    vsc.dist(self.a, [
                        vsc.weight((10,15),  80),
                        vsc.weight((20,30),  40),
                        vsc.weight((40,70),  20),
                        vsc.weight((80,100), 10)])
                with vsc.else_then:
                    vsc.dist(self.a, [
                        vsc.weight((10,15),  10),
                        vsc.weight((20,30),  20),
                        vsc.weight((40,70),  40),
                        vsc.weight((80,100), 80)])
                
        c = my_c()
        
        hist = 4*[0]
        c.b = 1
        for i in range(100):
            c.randomize()
            if c.a >= 10 and c.a <= 15:
                hist[0] += 1
            elif c.a >= 20 and c.a <= 30:
                hist[1] += 1
            elif c.a >= 40 and c.a <= 70:
                hist[2] += 1
            elif c.a >= 80 and c.a <= 100:
                hist[3] += 1
            else:
                self.fail("Value " + str(c.a) + " illegal")
        print("hist: " + str(hist))

    def test_dist_array_elems(self):

        @vsc.randobj 
        class my_c(object):
            def __init__(self): 
                self.a = vsc.rand_list_t(vsc.bit_t(7),4)
              
            @vsc.constraint 
            def dist_a(self):
                with vsc.foreach(self.a, idx=True) as i:
                    vsc.dist(self.a[i], [ 
                        vsc.weight(1, 10), 
                        vsc.weight(2, 20), 
                        vsc.weight(4, 40), 
                        vsc.weight(8, 80)])

        my = my_c()

        # Randomize
        hist = []
        for i in range(4):
            hist.append([0]*4)
            
        for i in range(400):
            my.randomize(debug=0)
            for i in range(4):
                v = my.a[i]
                if v == 1:
                    hist[i][0] += 1
                elif v == 2:
                    hist[i][1] += 1
                elif v == 4:
                    hist[i][2] += 1
                elif v == 8:
                    hist[i][3] += 1
                else:
                    raise Exception("Value[%d] %d out of range" % (i, v))
                    
        for i in range(len(hist)):
            print("hist[" + str(i) + "] " + str(hist[i]))
            for j in range(len(hist[i])):
                if j > 0:
                    self.assertGreater(hist[i][j], hist[i][j-1])
                    
    def test_dist_array_elems_range(self):
        class my_e(IntEnum):
            A = 0
            B = auto()
            C = auto()
            D = auto()
   
        @vsc.randobj 
        class my_c(object):
            def __init__(self): 
                self.a = vsc.rand_enum_t(my_e)
                #self.a = vsc.rand_list_t(vsc.bit_t(7),15)
                #self.a = vsc.rand_uint8_t() 
              
            @vsc.constraint 
            def dist_a(self):
#                vsc.dist(self.a, [vsc.weight(vsc.rng(my_e.A, my_e.C),10), vsc.weight(my_e.D, 20)]) 
                vsc.dist(self.a, [vsc.weight(vsc.rng(my_e.A, my_e.C),3), vsc.weight(my_e.D, 1)]) 

        my = my_c()
        
        hist = [0]*4

        # Randomize
        for i in range(100):
#            print(">======= " + str(i) + " ========")
            my.randomize()
#            print("<======= " + str(i) + " ========")
            hist[int(my.a)] += 1
#            print("MY ITEM : ",i+1)
#            print(my.a)    

        print("hist: " + str(hist))
        for v in hist:
            self.assertNotEqual(v, 0)
    
    def test_dist_soft_0(self):

        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                pass
                # vsc.soft(self.a < 5) #Case A: this is fine since it is a looser bound than the dist constraint
                # vsc.soft(self.a > 5) #Case B: this throws off distribution; would have expected this soft constraint to be ignored as if it were commented out and distribution to follow 1:97:1:1)
                # self.a > 5 #Case C: this causes a constraint error since this value domain is disjoint from that of the dist constraint
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  1),
                    vsc.weight(1,  97),
                    vsc.weight(2,  1),
                    vsc.weight(3,  1),
                    #vsc.weight(20, 10000) #Case D: this throws off distribution when combined with the line labeled below (the larger the weight, the worse -- seems that the weights get redistributed unevenly)
            ])

        hist = {}
        total_cnt = 0

        def add_to_hist(val):
            nonlocal hist
            nonlocal total_cnt
            total_cnt += 1
            if val not in hist: hist[val] = 0
            hist[val] += 1

        def print_dist(val):
            nonlocal hist
            nonlocal total_cnt
            print(f"{val}: {hist[val]} " + "(%.1f%%)" %(hist[val] / total_cnt * 100))

        item = my_item()
        for i in range(1000):
            with item.randomize_with() as it:
                pass
                #it.a <= 5 #Case D
            add_to_hist(item.a)

        for key in sorted(hist.keys()):
            print_dist(key)
            
        self.assertIn(0, hist.keys())
        self.assertIn(1, hist.keys())
        self.assertIn(2, hist.keys())
        self.assertIn(3, hist.keys())

        # We expect 97% distribution, but only worry about
        # cases below 90%
        self.assertGreater(hist[1]/total_cnt, 0.90)
        
    def test_dist_soft_1(self):

        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                pass
                vsc.soft(self.a < 5) #Case A: this is fine since it is a looser bound than the dist constraint
                # vsc.soft(self.a > 5) #Case B: this throws off distribution; would have expected this soft constraint to be ignored as if it were commented out and distribution to follow 1:97:1:1)
                # self.a > 5 #Case C: this causes a constraint error since this value domain is disjoint from that of the dist constraint
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  1),
                    vsc.weight(1,  97),
                    vsc.weight(2,  1),
                    vsc.weight(3,  1),
                    #vsc.weight(20, 10000) #Case D: this throws off distribution when combined with the line labeled below (the larger the weight, the worse -- seems that the weights get redistributed unevenly)
            ])

        hist = {}
        total_cnt = 0

        def add_to_hist(val):
            nonlocal hist
            nonlocal total_cnt
            total_cnt += 1
            if val not in hist: hist[val] = 0
            hist[val] += 1

        def print_dist(val):
            nonlocal hist
            nonlocal total_cnt
            print(f"{val}: {hist[val]} " + "(%.1f%%)" %(hist[val] / total_cnt * 100))

        item = my_item()
        for i in range(1000):
            with item.randomize_with() as it:
                pass
                #it.a <= 5 #Case D
            add_to_hist(item.a)

        for key in sorted(hist.keys()):
            print_dist(key)
            
        self.assertIn(0, hist.keys())
        self.assertIn(1, hist.keys())
        self.assertIn(2, hist.keys())
        self.assertIn(3, hist.keys())

        # We expect 97% distribution, but only worry about
        # cases below 90%
        self.assertGreater(hist[1]/total_cnt, 0.90)
        
    def test_dist_soft_2(self):

        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                pass
                # vsc.soft(self.a < 5) #Case A: this is fine since it is a looser bound than the dist constraint
                vsc.soft(self.a > 5) #Case B: this throws off distribution; would have expected this soft constraint to be ignored as if it were commented out and distribution to follow 1:97:1:1)
                # self.a > 5 #Case C: this causes a constraint error since this value domain is disjoint from that of the dist constraint
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  1),
                    vsc.weight(1,  97),
                    vsc.weight(2,  1),
                    vsc.weight(3,  1),
                    #vsc.weight(20, 10000) #Case D: this throws off distribution when combined with the line labeled below (the larger the weight, the worse -- seems that the weights get redistributed unevenly)
            ])

        hist = {}
        total_cnt = 0

        def add_to_hist(val):
            nonlocal hist
            nonlocal total_cnt
            total_cnt += 1
            if val not in hist: hist[val] = 0
            hist[val] += 1

        def print_dist(val):
            nonlocal hist
            nonlocal total_cnt
            print(f"{val}: {hist[val]} " + "(%.1f%%)" %(hist[val] / total_cnt * 100))

        item = my_item()
        for i in range(1000):
            with item.randomize_with() as it:
                pass
                #it.a <= 5 #Case D
            add_to_hist(item.a)

        for key in sorted(hist.keys()):
            print_dist(key)
            
        self.assertIn(0, hist.keys())
        self.assertIn(1, hist.keys())
        self.assertIn(2, hist.keys())
        self.assertIn(3, hist.keys())

        # We expect 97% distribution, but only worry about
        # cases below 90%
        self.assertGreater(hist[1]/total_cnt, 0.90)        

    def disabled_test_dist_soft_3(self):

        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                pass
                # vsc.soft(self.a < 5) #Case A: this is fine since it is a looser bound than the dist constraint
                # vsc.soft(self.a > 5) #Case B: this throws off distribution; would have expected this soft constraint to be ignored as if it were commented out and distribution to follow 1:97:1:1)
#                self.a > 5 #Case C: this causes a constraint error since this value domain is disjoint from that of the dist constraint
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  1),
                    vsc.weight(1,  97),
                    vsc.weight(2,  1),
                    vsc.weight(3,  1),
                    vsc.weight(20, 10000) #Case D: this throws off distribution when combined with the line labeled below (the larger the weight, the worse -- seems that the weights get redistributed unevenly)
            ])

        hist = {}
        total_cnt = 0

        def add_to_hist(val):
            nonlocal hist
            nonlocal total_cnt
            total_cnt += 1
            if val not in hist: hist[val] = 0
            hist[val] += 1

        def print_dist(val):
            nonlocal hist
            nonlocal total_cnt
            print(f"{val}: {hist[val]} " + "(%.1f%%)" %(hist[val] / total_cnt * 100))

        item = my_item()
        for i in range(1000):
            with item.randomize_with() as it:
                pass
                it.a <= 5 #Case D
            add_to_hist(item.a)

        for key in sorted(hist.keys()):
            print_dist(key)
            
        self.assertIn(0, hist.keys())
        self.assertIn(1, hist.keys())
        self.assertIn(2, hist.keys())
        self.assertIn(3, hist.keys())

        # We expect 97% distribution, but only worry about
        # cases below 90%
        self.assertGreater(hist[1]/total_cnt, 0.90)        

    def test_compound_array(self):
        import vsc 

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

            @vsc.constraint
            def parent_c(self):
                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 

                with vsc.foreach(self.c1, idx=True) as i:
                    self.c1[i].a[0].value == self.c2[i].x[0].value


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
    
            @vsc.constraint
            def test_c(self):
                self.a[0].value < self.a[1].value

                # Error here
                vsc.dist(self.a[0].value, [
                    vsc.weight(1, 10),
                    vsc.weight(2, 20),
                    vsc.weight(4, 40),
                    vsc.weight(8, 80)])

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
        inst.randomize()
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)
        
    def test_random_stability(self):
        import vsc
        
        class Base():
            def __init__(self):
                super().__init__()
                # Not used in a constraint
                self.nc_one = vsc.rand_uint16_t()
                self.nc_two = vsc.rand_uint16_t()
        
                # Used in a constraint
                self.con_one = vsc.rand_uint16_t()
                self.con_two = vsc.rand_uint16_t()
        
            def __repr__(self):
                return f'NC: {self.nc_one}, {self.nc_two}    Con: {self.con_one}, {self.con_two}'
        
        @vsc.randobj
        class Without_Dist(Base):
            @vsc.constraint
            def sample_c(self):
                self.con_one < self.con_two
        
        @vsc.randobj
        class With_Dist(Base):
            @vsc.constraint
            def sample_c(self):
                self.con_one < self.con_two
                vsc.dist(self.con_one, [
                    vsc.weight(0, 33),
                    vsc.weight((1, 8192), 60),
                    vsc.weight((8193, (2**16)-1), 7)])
        
        def show_it(obj, rs):
            obj.set_randstate(rs)
            obj.randomize()
            nc_one_1 = obj.nc_one
            nc_two_1 = obj.nc_two
            con_one_1 = obj.con_one
            con_two_1 = obj.con_two
            print(f'Try 1: {obj}')
            obj.set_randstate(rs)
            obj.randomize()
            nc_one_2 = obj.nc_one
            nc_two_2 = obj.nc_two
            con_one_2 = obj.con_one
            con_two_2 = obj.con_two
            print(f'Try 2: {obj}')
            if nc_one_1 != nc_one_2 or nc_two_1 != nc_two_2 or con_one_1 != con_one_2 or con_two_1 != con_two_2:
                self.fail("Error: Mismatch")
            print()
        
        def run_obj(obj):
            cnt = 6
        
            print(f'Using {type(obj).__name__}')
            print('------------------')
            for n in range(cnt):
                rs = vsc.RandState.mkFromSeed(n)
                show_it(obj, rs)
        
        obj = Without_Dist()
        run_obj(obj)
        obj = With_Dist()
        run_obj(obj)        
        
        