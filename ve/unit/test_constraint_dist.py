'''
Created on Aug 9, 2020

@author: ballance
'''

from enum import Enum, auto, IntEnum
import vsc

from vsc_test_case import VscTestCase


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
            my.randomize()
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
                    raise Exception("Value " + str(v) + " out of range")
                    
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
    
    
    
        
            
