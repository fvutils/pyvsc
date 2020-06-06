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
        
    def test_histogram_lt(self):
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
                
                self.rand_bit_1 < self.rand_bit_2

        rand_obj = fifo_driver_random()
        NbLoops = 3000

        for i in range(NbLoops):

            rand_obj.randomize()

            # random, unsigned (bit), and L-bits wide
            self.assertLess(rand_obj.rand_bit_1, 10)
            self.assertLess(rand_obj.rand_bit_2, 30)
            self.assertLess(rand_obj.rand_bit_3, 100)
            rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] = rand_obj.rand_bit_1_hist[rand_obj.rand_bit_1] + 1
            rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] = rand_obj.rand_bit_2_hist[rand_obj.rand_bit_2] + 1
            rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] = rand_obj.rand_bit_3_hist[rand_obj.rand_bit_3] + 1
            rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] = rand_obj.rand_bit_4_hist[rand_obj.rand_bit_4] + 1

        print("\n\nself.rand_bit_1 histogram is:", rand_obj.rand_bit_1_hist[0:9])
        print("\n\nself.rand_bit_2 histogram is:", rand_obj.rand_bit_2_hist[1:29])
        print("\n\nself.rand_bit_3 histogram is:", rand_obj.rand_bit_3_hist[0:99])
        print("\n\nself.rand_bit_4 histogram is:", rand_obj.rand_bit_4_hist)
        
        z_cnt=0
        for v in rand_obj.rand_bit_1_hist[0:9]:
            if v == 0:
                z_cnt += 1
        self.assertEqual(z_cnt, 0)
        z_cnt=0
        for v in rand_obj.rand_bit_2_hist[1:29]:
            if v == 0:
                z_cnt += 1
        self.assertEqual(z_cnt, 0)
        z_cnt=0
        for v in rand_obj.rand_bit_3_hist[0:99]:
            if v == 0:
                z_cnt += 1
        self.assertEqual(z_cnt, 0)
        z_cnt=0
        for v in rand_obj.rand_bit_4_hist:
            if v == 0:
                z_cnt += 1
        # Know that it's likely to take ~2560 to hit all
        self.assertLess(z_cnt, 8)
        self.assertEqual(z_cnt, 0)

