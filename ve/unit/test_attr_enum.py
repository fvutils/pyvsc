'''
Created on Jun 24, 2020

@author: ballance
'''
from enum import Enum, auto, IntEnum

import vsc
from vsc_test_case import VscTestCase


class TestAttrEnum(VscTestCase):
    
    def test_rand_plain_enum(self):
        
        class my_e(Enum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                
        inst = my_s()
        
        for i in range(100):
            inst.randomize()

    def test_rand_plain_enum_hist(self):
        
        class my_e(Enum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                
        inst = my_s()
        
        for i in range(100):
            inst.randomize()
        
    def test_rand_int_enum(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                self.c = vsc.rand_uint8_t()

        a_hist = [0]*2
        inst = my_s()
        
        for i in range(100):
            inst.randomize()
            if inst.a == my_e.A:
                a_hist[0] += 1
            else:
                a_hist[1] += 1
            
        print("hist: " + str(a_hist))
        
        delta = abs(a_hist[0] - a_hist[1])
        self.assertLess(delta, 50)
            
    def test_rand_int_enum_hist(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                self.c = vsc.rand_uint8_t()

        a_hist = [0]*2
        
        inst = my_s()
        
        for i in range(100):
            inst.randomize()
            if inst.a == my_e.A:
                a_hist[0] += 1
            else:
                a_hist[1] += 1
                
        print("a_hist: " + str(a_hist))
        
        delta = abs(a_hist[0] - a_hist[1])
        self.assertLess(delta, 25)
       
    def test_enum_setval(self):
        class my_e(Enum):
            A = auto()
            B = auto()
        var = vsc.enum_t(my_e)
        var.set_val(my_e.A)

        self.assertEqual(var.get_val(), my_e.A)
        
        