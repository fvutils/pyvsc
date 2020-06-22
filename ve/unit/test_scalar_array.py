'''
Created on Jun 9, 2020

@author: ballance
'''
import time

import vsc
from vsc.types import uint8_t
from vsc_test_case import VscTestCase


class TestScalarArray(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.rand_list_t(uint8_t(), 10)
                
            @vsc.constraint
            def my_l_c(self):
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                

    def test_randsize_1(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.randsz_list_t(uint8_t())
                
            @vsc.constraint
            def my_l_c(self):
                self.my_l.size == 10
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
            
            self.assertEqual(it.my_l.size, 10)
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                
            
    def test_randsize_2(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.randsz_list_t(uint8_t())
                
            @vsc.constraint
            def my_l_c(self):
                self.my_l.size > 0
                self.my_l.size <= 4
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        size_hist = [0]*4
        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
            
            self.assertLessEqual(it.my_l.size, 4)

            size_hist[it.my_l.size-1] += 1           
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        print("Size Hist: " + str(size_hist))
        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                            
            
    def test_large_arrays(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l_1 = vsc.rand_list_t(uint8_t(), 1000)
                self.my_l_2 = vsc.rand_list_t(uint8_t(), 1000)
                
            @vsc.constraint
            def my_l_c(self):
                with vsc.foreach(self.my_l_1) as it:
                    it < 10
                with vsc.foreach(self.my_l_2) as it:
                    it < 10
                    
        it = my_item_c()

        count = 4
        start_m = int(round(time.time() * 1000))
        for i in range(count):
            it.randomize()
            
            for i,e in enumerate(it.my_l_1):
                self.assertLess(e, 10)
            for i,e in enumerate(it.my_l_2):
                self.assertLess(e, 10)
                
        end_m = int(round(time.time() * 1000))
                
        delta_m = (end_m-start_m)
        count_per_s = (count*1000)/delta_m
        ms_per_i = (delta_m/count)
       
        print("Delta: " + str(delta_m)) 
        print("Items/s: " + str(count_per_s) + " Time/item (ms): " + str(ms_per_i))

