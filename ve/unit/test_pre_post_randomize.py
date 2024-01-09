'''
Created on Jul 18, 2020

@author: ballance
'''

import vsc
from vsc_test_case import VscTestCase
from enum import Enum, auto


class TestPreProstRandomize(VscTestCase):
    
    def test_post_rand_list_mod(self):
        
        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()
            
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.b = vsc.rand_enum_t(my_e);
                self.temp = vsc.list_t(vsc.enum_t(my_e))
            
            @vsc.constraint
            def ab_c(self):
                self.b in vsc.rangelist(my_e.A, my_e.D)
                
            def post_randomize(self):
                print("post_randomize")
                print("PR: self.b =", self.b)
                print("PR: Before Append: self.temp=", self.temp)
                self.temp.append(self.b)
                print("PR: After Append self.temp=", self.temp)
                
        my = my_s()
        
        for i in range(5):
            print("--> randomize(%d)" % i)
            my.randomize()
            self.assertEqual(len(my.temp), i+1)
            print("<-- randomize(%d)" % i)
        

    def test_pre_rand(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)

            @vsc.constraint
            def a_five_c(self):
                self.a == 5

            @vsc.constraint
            def a_not_five_c(self):
                self.a != 5

            def pre_randomize(self):
                self.a_not_five_c.constraint_mode(not self.a_not_five_c.constraint_model.enabled)
                self.a_five_c.constraint_mode(not self.a_five_c.constraint_model.enabled)

        my = my_s()

        # Alternate between constraints in pre_rand to test randomize caching
        my.a_not_five_c.constraint_mode(False)

        for i in range(5):
            my.randomize()
            print(my.a, my.a_five_c.constraint_model.enabled)
            if my.a_five_c.constraint_model.enabled:
                self.assertEqual(my.a, 5)
            else:
                self.assertNotEqual(my.a, 5)