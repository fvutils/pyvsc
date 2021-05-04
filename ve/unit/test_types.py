'''
Created on Apr 24, 2021

@author: mballance
'''
import vsc
import random
from vsc_test_case import VscTestCase

class TestTypes(VscTestCase):
    
    def test_signed(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.rand_int_t(32), 3)  # intentionally using rand_int_t because I want signed

            @vsc.constraint
            def cx(self):
                with vsc.foreach(self.x, idx=True) as i:
                    self.x[i] >= -32768
                    self.x[i] <= 32768
                    
                    self.x[i] == i-27

        c = cl()
        c.randomize()
        for ii,i in enumerate(c.x):
            print(i)
            self.assertEquals(i, ii-27)
            
    def test_nonrand_signed_list_init(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.list_t(vsc.int_t(16), init=[random.randint(-2, -1) for _ in range(1)])

        c = cl()
        c.randomize()
        print("c.x[0]=" + str(c.x[0]))
        if c.x[0] > 0:
            raise RuntimeError('Value greater than zero')            
        
    def test_nonrand_signed_list_set(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.list_t(vsc.int_t(16), init=[-2,-1])

        c = cl()
        
        self.assertEqual(c.x[0], -2)
        self.assertEqual(c.x[1], -1)
        
        c.x[0] = 5
        self.assertEqual(c.x[0], 5)
        c.x[0] = -7
        self.assertEqual(c.x[0], -7)

    def test_nonrand_signed_list_append(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.list_t(vsc.int_t(16), init=[-2,-1])

        c = cl()
        
        self.assertEqual(c.x[0], -2)
        self.assertEqual(c.x[1], -1)

        c.x.append(-7)        
        self.assertEqual(c.x[2], -7)

    def test_nonrand_unsigned_list_append(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.list_t(vsc.bit_t(16), init=[0, 1])

        c = cl()
        
        self.assertEqual(c.x[0], 0)
        self.assertEqual(c.x[1], 1)

        c.x.append(0x12345)
        self.assertEqual(c.x[2], 0x2345)

    def test_nonrand_signed_init(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.int_t(16, i=-2))

        c = cl()
        
        self.assertEqual(c.x, -2)
        
    def test_nonrand_signed_set(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.int_t(16, i=-2))

        c = cl()
        
        self.assertEqual(c.x, -2)
        c.x = -3
        self.assertEqual(c.x, -3)
        
    def test_nonrand_signed_pluseq(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.int_t(16, i=-2))

        c = cl()
        
        self.assertEqual(c.x, -2)
        c.x = -1
        self.assertEqual(c.x, -1)
        c.x += 1
        self.assertEqual(c.x, 0)
        
    def test_nonrand_signed_minuseq(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.int_t(16, i=-2))

        c = cl()
        
        self.assertEqual(c.x, -2)
        c.x = 0
        self.assertEqual(c.x, 0)
        c.x -= 1
        self.assertEqual(c.x, -1)
        
    def test_nonrand_unsigned_init(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.bit_t(16, i=0x12345))

        c = cl()
        
        self.assertEqual(c.x, 0x2345)
        
    def test_nonrand_unsigned_set(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.bit_t(16, i=0x12345))

        c = cl()
        
        self.assertEqual(c.x, 0x2345)
        c.x = 0x23456
        self.assertEqual(c.x, 0x3456)

    def test_nonrand_unsigned_minuseq(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.bit_t(16, i=0x12345))

        c = cl()
        
        self.assertEqual(c.x, 0x2345)
        c.x = 0x0
        self.assertEqual(c.x, 0x0)
        c.x -= 1
        self.assertEqual(c.x, 0xFFFF)
        
    def test_nonrand_unsigned_pluseq(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.attr(vsc.bit_t(16, i=0x12345))

        c = cl()
        
        self.assertEqual(c.x, 0x2345)
        c.x = 0xFFFF
        self.assertEqual(c.x, 0xFFFF)
        c.x += 1
        self.assertEqual(c.x, 0x0)
        
    def test_rand_unsigned(self):

        @vsc.randobj
        class cl:
            def __init__(self):
                self.x = vsc.rand_attr(vsc.bit_t(16))

        c = cl()
        
        with c.randomize_with() as it:
            it.x == 0xFFFF
        
        self.assertEqual(c.x, 0xFFFF)
