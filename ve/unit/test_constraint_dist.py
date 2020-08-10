'''
Created on Aug 9, 2020

@author: ballance
'''

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
        
