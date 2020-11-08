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
        n_iter = 32*10
        
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
        n_iter = 32*10
        
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
        n_iter = 32*10
        
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
        n_iter = 32*20
        
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
        n_iter = 32*20
        
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
