'''
Created on Mar 26, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestConstraintExpr(VscTestCase):
    
    def test_eq(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a == it.b
        self.assertEqual(my_i.a, my_i.b)
        
    def test_ne(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a != it.b
        self.assertNotEqual(my_i.a, my_i.b)        
        
    def test_gt(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a > it.b
        self.assertGreater(my_i.a, my_i.b)        
        
    def test_ge(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a >= it.b
        self.assertGreaterEqual(my_i.a, my_i.b)        
        
    def test_lt(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a < it.b
        self.assertLess(my_i.a, my_i.b)

    def test_le(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.a <= it.b
        self.assertLessEqual(my_i.a, my_i.b)        

    def test_add(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a + it.b)
        self.assertEqual(my_i.c, (my_i.a+my_i.b))

    def test_sub(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128
                self.a > self.b
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a - it.b)
        self.assertEqual(my_i.c, (my_i.a-my_i.b))

    def test_div(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 128
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a / it.b)
        self.assertEqual(my_i.c, int(my_i.a/my_i.b))

    def test_mul(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 64
                self.b != 0
                self.b < 4
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a * it.b)
        self.assertEqual(my_i.c, (my_i.a*my_i.b))

    def test_mod(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 128
                self.b != 0
                self.b < 8
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a % it.b)
        self.assertEqual(my_i.c, (my_i.a%my_i.b))

    def test_and(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a & it.b)
        self.assertEqual(my_i.c, (my_i.a&my_i.b))

    def test_or(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a | it.b)
        self.assertEqual(my_i.c, (my_i.a|my_i.b))

    def test_sll(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.a < 4
                self.b != 0
                self.b < 4
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a << it.b)
        self.assertEqual(my_i.c, (my_i.a<<my_i.b))

    def test_srl(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a >> it.b)
        self.assertEqual(my_i.c, (my_i.a>>my_i.b))

    def test_xor(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == (it.a ^ it.b)
        self.assertEqual(my_i.c, (my_i.a^my_i.b))

    def test_slice(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == it.a[1]
        self.assertEqual(my_i.c, (my_i.a & 0x2) >> 1)
        
    def test_slice2(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a != 0
                self.b != 0
                self.c != 0
                
        my_i = my_c()
        with my_i.randomize_with() as it:
            it.c == it.a[2:1]
        self.assertEqual(my_i.c, (my_i.a & 0x6) >> 1)
        
