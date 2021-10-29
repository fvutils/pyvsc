'''
Created on Oct 12, 2021

@author: mballance
'''
import vsc
from vsc.model.rand_state import RandState
from vsc_test_case import VscTestCase


class TestRandState(VscTestCase):
    
    def test_init_state(self):

        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2 = []
        
        rs1 = RandState(0)
        ci.set_randstate(rs1)
        for _ in range(100):
            ci.randomize()
            v1.append((ci.a,ci.b))

        rs2 = RandState(100)
        ci.set_randstate(rs2)
        
        for _ in range(100):
            ci.randomize()
            v2.append((ci.a,ci.b))

        # Check that two lists are not exactly equal
        all_equal = True
        for i in range(len(v1)):
            if v1[i][0] != v2[i][0] or v1[i][1] != v2[i][1]:
                all_equal = False
                break
        self.assertFalse(all_equal)
        
    def test_same_seed_str(self):
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2 = []

        print("Iteration 1")        
        rs1 = RandState.mkFromSeed(10, "abc")
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v1.append((ci.a,ci.b))

        print("Iteration 2") 
        rs2 = RandState.mkFromSeed(10, "abc")
        ci.set_randstate(rs2)
        for _ in range(10):
            ci.randomize()
            v2.append((ci.a,ci.b))

        # Check that two lists are not exactly equal
        all_equal = True
        for i in range(len(v1)):
            print("[%d] v1=(%d,%d) v2=(%d,%d)" % (
                  i, v1[i][0], v1[i][1],
                  v2[i][0], v2[i][1]))
            if v1[i][0] != v2[i][0] or v1[i][1] != v2[i][1]:
                all_equal = False
#                break
        self.assertTrue(all_equal)        

    def test_diff_seed(self):
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2_1 = []
        v2_2 = []

        print("Iteration 1")        
        rs1 = RandState.mkFromSeed(0)
        
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v1.append((ci.a,ci.b))
        
        rand_s = rs1.randint(0, 1000000)
        
        rs2_1 = RandState.mkFromSeed(rand_s)
        rs2_2 = RandState.mkFromSeed(rand_s)
        
        print("Iteration 2_1") 
        ci.set_randstate(rs2_1)
        for _ in range(10):
            ci.randomize()
            v2_1.append((ci.a,ci.b))
            
        print("Iteration 2_2") 
        ci.set_randstate(rs2_2)
        for _ in range(10):
            ci.randomize()
            v2_2.append((ci.a,ci.b))

        # Check that two lists are not exactly equal
        all_equal = True
        for i in range(len(v1)):
            print("[%d] v2_1=(%d,%d) v2_2=(%d,%d)" % (
                  i, v2_1[i][0], v2_1[i][1],
                  v2_2[i][0], v2_2[i][1]))
            if v2_1[i][0] != v2_2[i][0] or v2_1[i][1] != v2_2[i][1]:
                all_equal = False
                break
        self.assertTrue(all_equal)
        
        # Check that we have differences from the first set
        all_equal = True
        for i in range(len(v1)):
            print("[%d] v1=(%d,%d) v2_2=(%d,%d)" % (
                  i, v1[i][0], v1[i][1],
                  v2_2[i][0], v2_2[i][1]))
            if v1[i][0] != v2_2[i][0] or v1[i][1] != v2_2[i][1]:
                all_equal = False
                break
        self.assertFalse(all_equal)
        
    def test_rerun_same_seed(self):
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2 = []

        print("Iteration 1")        
        rs1 = RandState(0)
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v1.append((ci.a,ci.b))

        print("Iteration 2") 
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v2.append((ci.a,ci.b))

        # Check that two lists are not exactly equal
        all_equal = True
        for i in range(len(v1)):
            print("[%d] v1=(%d,%d) v2=(%d,%d)" % (
                  i, v1[i][0], v1[i][1],
                  v2[i][0], v2[i][1]))
            if v1[i][0] != v2[i][0] or v1[i][1] != v2[i][1]:
                all_equal = False
#                break
        self.assertTrue(all_equal)        

