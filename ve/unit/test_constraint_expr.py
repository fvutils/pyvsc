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
                self.b = vsc.uint8_t()
                print("__init__ a=%s" %str(self.a))
                
        my_i = my_c()
        for i in range(2):
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
        with my_i.randomize_with(debug=1) as it:
#            it.c == (it.a + it.b)
            it.c == (it.a + it.b)
            pass
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
        for i in range(100):
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
        self.assertNotEqual(my_i.b, 0)
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
        
    def test_unary_not(self):
        import vsc
        import random
        random.seed(0)

        @vsc.randobj
        class Test:
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def test_c(self):
                self.a == ~self.b 

        inst = Test()
        inst.randomize()
        print("a =", inst.a, "b =", inst.b)
        print("Binary representation of a:", f"{inst.a:b}")
        print("Binary representation of b:", f"{inst.b:b}")        
        self.assertEqual(inst.a, ~inst.b & 0xFF)

    def test_partselect_compound_array(self):
        import vsc 

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(10):    
                    self.c1.append(vsc.attr(Child1()))

                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(10):
                    self.c2.append(vsc.attr(Child2()))

            # Fails
            @vsc.constraint
            def parent_c(self):
                self.c1[0].test_bit[4:2] == 0
       
        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(5):    
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(5):    
                    self.b.append(vsc.attr(Field('b', 10)))

                self.test_bit =  vsc.rand_bit_t(8)

            @vsc.constraint
            def test_c(self):
                #self.test_bit[4:2] == 0
                self.a[0].value < self.a[1].value

        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.attr(Field('x', 10)))
                for i in range(5):    
                    self.x.append(vsc.attr(Field('x', 10)))

                self.y = vsc.rand_list_t(vsc.attr(Field('y', 10)))
                for i in range(5):    
                    self.y.append(vsc.attr(Field('y', 10)))
    
            @vsc.constraint
            def test_c(self):
                self.x[0].value < self.x[1].value

        inst=Parent()
        inst.randomize()
        print(f"{inst.c1[0].test_bit:b}")
        
        self.assertEqual((inst.c1[0].test_bit >> 2) & 0x3, 0)
