'''
Created on Jul 30, 2020

@author: ballance
'''

from enum import IntEnum, auto

import vsc
from vsc_test_case import VscTestCase


class TestFieldStandalone(VscTestCase):
    
    def test_simple_int(self):
        a = vsc.rand_uint8_t()
        
        print("a=" + str(a.get_val()))
        self.assertEqual(a.get_val(), 0);
        
    def test_simple_rand(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        vsc.randomize(a, b)
                
        print("a=" + str(a.get_val()) + " b=" + str(b.get_val()))
        
    def test_simple_rand_inline1(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a < b
            self.assertLess(a.get_val(), b.get_val())
            
    def test_simple_rand_inline2(self):
        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a < b
            self.assertLess(a.val, b.val)

    def test_simple_intenum(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()
            
        a = vsc.rand_enum_t(my_e)
        b = vsc.rand_enum_t(my_e)

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a != b
            self.assertNotEqual(a.val, b.val)
            
    def test_simple_intenum2(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()
            
        a = vsc.rand_enum_t(my_e)
        b = vsc.rand_enum_t(my_e)

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a != b
            self.assertNotEqual(a.get_val(), b.get_val())
            
    def test_setval_intenum(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()
            
        a = vsc.rand_enum_t(my_e)
        b = vsc.rand_enum_t(my_e)
        
        a.val = my_e.A
        b.val = my_e.B

        self.assertNotEqual(a.get_val(), b.get_val())
        self.assertEqual(a.val, a.get_val())
        self.assertEqual(a.val, my_e.A)
        self.assertEqual(b.val, b.get_val())
        self.assertEqual(b.val, my_e.B)
        
    def test_standalone_setbit(self):
        a = vsc.rand_uint16_t()

        a[15] = 1
        
        self.assertEqual(a.val, (1 << 15))
        
    def test_standalone_setpart(self):
        a = vsc.rand_uint16_t()

        a[15:8] = 1
        
        self.assertEqual(a.val, (1 << 8))

    def test_standalone_getbit(self):
        a = vsc.rand_uint16_t()

        a.val = (1 << 15)
        
        self.assertEqual(a[15], 1)
        
    def test_standalone_getpart(self):
        a = vsc.rand_uint16_t()

        a.val = (25 << 8)
        
        self.assertEqual(a[15:8], 25)

    def test_obj_getpart(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint16_t()

        c = my_c()
        c.a = (25 << 8)

        with vsc.raw_mode():        
            self.assertEqual(c.a[15:8], 25)

