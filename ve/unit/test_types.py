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
        
    def test_overflow(self):
        import vsc
        import random
        random.seed(0)

        @vsc.randobj
        class Test:
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()

            @vsc.constraint
            def test_c(self):
#                self.a < 256
#                self.b < 256
                self.a*self.b == 50

        inst = Test()
        inst.randomize()
        
        a = inst.a
        b = inst.b
        
        print("a =", inst.a, "b =", inst.b)
        print("Binary representation of a*b:", f"{inst.a*inst.b:b}")
        print("Binary representation of 50:", f"{50:b}")        
        self.assertEqual(a*b, 50)

    def test_constant_resizing(self):
        """Test that a literal properly up-sizes the expression"""
        import vsc
        import random
        random.seed(0)

        @vsc.randobj
        class Test:
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()

            @vsc.constraint
            def test_c(self):
                # Error
                self.a*self.b == 256

                # Works
                #self.a*self.b < 256

        inst = Test()
        inst.randomize()
        print("a =", inst.a, "b =", inst.b)

    def test_bit_subscript_alt(self):
        import vsc
 
        @vsc.randobj
        class my_item_c(object):
            def __init__(self):
                self.a = vsc.bit_t(8)
    
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    it=my_item_c()))

                self.cp_my = vsc.coverpoint(lambda: ((self.it.a >> 2) & 0x3F),
                                            bins={
                                                "a": vsc.bin_array([], [0, 3])
                                            }
                                            )
        # Create an instance of the covergroup
        my_cg_i = my_cg()
        # Create an instance of the item class
        my_item_i = my_item_c()
        my_cg_i.sample(my_item_i)
        
    def test_bit_subscript(self):
        import vsc
 
        @vsc.randobj
        class my_item_c(object):
            def __init__(self):
                self.a = vsc.bit_t(8)
    
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    it=my_item_c()))

                self.cp_my = vsc.coverpoint(lambda:self.it.a[7:2],
                                            bins={
                                                "a": vsc.bin_array([], [0, 3])
                                            }
                                            )
        # Create an instance of the covergroup
        my_cg_i = my_cg()
        # Create an instance of the item class
        my_item_i = my_item_c()
        my_cg_i.sample(my_item_i)    
