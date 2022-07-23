'''
Created on Sep 26, 2020

@author: ballance
'''
from enum import Enum
import vsc

from vsc_test_case import VscTestCase


class TestConstraintIfElse(VscTestCase):
    
    def test_if_elseif_enum_cond1(self):
        class my_e(Enum):
            A = 0
            B = 1
            C = 2
            D = 3

        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.name = my_e.A
                self.a = vsc.rand_uint8_t(0)
                self.b = vsc.rand_list_t(vsc.enum_t(my_e), 4)
    

            @vsc.constraint
            def ab_c(self):
                with vsc.foreach(self.b, idx = True) as i:
                    with vsc.if_then(self.b[i] == my_e.A):
                        self.a == 0
                    with vsc.else_if(self.b[i] == my_e.B):
                        self.a == 1
              
        my = my_s()

        # Randomize
        for i in range(5):
            my.randomize()
            print("ITERATION : ",i+1)
            print(my.a, list(my.b))            

    def test_if_elseif_scalar_cond(self):

        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.a = vsc.uint8_t(1)
                self.b = vsc.rand_uint8_t()
    

            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a):
                    self.b == 0
                with vsc.else_then:
                    self.b == 1

        my = my_s()

        # Randomize
        for i in range(5):
            my.randomize()
            if my.a != 0:
                self.assertEquals(my.b, 0)
            else:
                self.assertEquals(my.b, 1)
            print("ITERATION : ", i+1, my.a, my.b)
            
    def test_if_then_foreach_nesting(self):
        
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.a = vsc.uint8_t(1)
                self.b = vsc.uint8_t(2)
                self.c = vsc.uint8_t(2)
                self.arr = vsc.rand_list_t(vsc.uint8_t(), 10)
                
            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a == 1):
                    with vsc.if_then(self.b == 2):
                        self.c == 2
                with vsc.foreach(self.arr, idx=True) as i:
                    with vsc.if_then(self.a == 1):
                        self.arr[i] == 1

        it = my_s()
        it.randomize()
