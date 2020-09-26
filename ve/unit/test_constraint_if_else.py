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
