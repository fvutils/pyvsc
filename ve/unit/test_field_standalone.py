'''
Created on Jul 30, 2020

@author: ballance
'''

import random
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

    def test_int_getpart_2(self):
        imm = vsc.rand_bit_t(4)
        imm.set_val(2)
        self.assertEqual(imm.get_val(), 2)
        self.assertEqual(imm[1:0], 2)

    def test_int_getpart_3(self):
        imm = vsc.rand_bit_t(4)
        imm.set_val(2)
        self.assertEqual(imm.get_val(), 2)
        self.assertEqual(imm[1], 1)
        
    def test_distweight(self):
        PCID = vsc.rand_uint16_t()
        
        hist1 = [0]*65536
        hist2 = [0]*65536

        items = 10000
        for i in range(items):
#            vsc.randomize(PCID)
            with vsc.randomize_with(PCID, debug=0):
#                PCID.inside(vsc.rng(1,65534))
                vsc.dist(PCID, [
                    vsc.weight(0, 1),
                    vsc.weight(vsc.rng(1,65534), 900),
                    vsc.weight(65535, 1)
                    ])
#            print("PCID: " + str(PCID.get_val()))
            hist1[PCID.get_val()] += 1 
            hist2[random.randint(1,65534)] += 1

        hist1_hit = 0
        hist2_hit = 0
        for e in hist1[1:65534]:
            if e != 0:
                hist1_hit += 1
        for e in hist2[1:65534]:
            if e != 0:
                hist2_hit += 1

        print("Items: %d hist1=%f hist2=%f" % (items, hist1_hit/65534, hist2_hit/65534))

        # Only check deeper if full random actually hit more than weighted
        if hist1_hit > hist2_hit:
            # Fail if plain randomization hit 15% more than weighted
            hist1_15p = int(hist1_hit * 0.15)
            self.assertLessEqual((hist1_hit-hist2_hit), hist1_15p)
            
#     def test_distweight_partitioned(self):
#         PCID = vsc.rand_uint16_t()
# 
#         for i in range(100):
#             print("==> randomize")
#             with vsc.randomize_with(PCID, debug=0):
#                 vsc.dist(PCID, [
#                     vsc.weight(0, 1),
#                     vsc.weight(vsc.rng(1,16383), 80),
#                     vsc.weight(vsc.rng(16384,32767), 30),
#                     vsc.weight(vsc.rng(32768,49151), 30),
#                     vsc.weight(vsc.rng(49152,65534), 30),
#                     vsc.weight(65535, 1)])
#             print("<== randomize")
#             print("PCID: %d" % int(PCID.get_val()))

    def test_bit_partselect(self):
            
        field = vsc.rand_uint32_t(0xFFEEAA55)
            
        self.assertEqual(field.get_val(), 0xFFEEAA55)
        self.assertEqual(field.get_val()[7:0], 0x55)
        self.assertEqual(field.get_val()[11:4], 0xA5)
        self.assertEqual(field.get_val()[31], 1)
        self.assertEqual(field.get_val()[0], 1)
        self.assertEqual(field.get_val()[8], 0)

    def test_width(self):
        import vsc

        my_bit_field    = vsc.rand_bit_t(16)  # 16-bit wide
        width           = my_bit_field.width
        print(f"The width of the bit field is: {width} bits")


        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.x = vsc.rand_bit_t(16)

            @vsc.constraint
            def ab_c(self):
                self.x in vsc.rangelist(1, 2, 4, 8)

            def print_width(self):
                with vsc.raw_mode():
                    width=self.x.width
                print(f'{width}')

        obj=my_s()

        for i in range(2):
            obj.randomize()
            obj.print_width()

