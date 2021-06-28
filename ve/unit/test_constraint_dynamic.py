'''
Created on Mar 26, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
import vsc

class TestConstraintDynamic(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a <= 100
                
            @vsc.dynamic_constraint
            def a_small(self):
                self.a in vsc.rangelist(vsc.rng(1,10))
                
            @vsc.dynamic_constraint
            def a_large(self):
                self.a in vsc.rangelist(vsc.rng(90,100))
                
        my_i = my_cls()

        for i in range(20):        
            with my_i.randomize_with() as it:
                it.a_small()
            print("a=" + str(my_i.a))
            self.assertGreaterEqual(my_i.a, 1)
            self.assertLessEqual(my_i.a, 10)
        
            with my_i.randomize_with() as it:
                it.a_large()
            print("a=" + str(my_i.a))
            self.assertGreaterEqual(my_i.a, 90)
            self.assertLessEqual(my_i.a, 100)

    def test_expr(self):
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a <= 100
                
            @vsc.dynamic_constraint
            def a_small(self):
                self.a in vsc.rangelist(vsc.rng(1,10))
                
            @vsc.dynamic_constraint
            def a_large(self):
                self.a in vsc.rangelist(vsc.rng(90,100))
                
        my_i = my_cls()

        for i in range(20):        
            with my_i.randomize_with() as it:
                it.a_small() | it.a_large()
            print("a=" + str(my_i.a))
            self.assertTrue(((my_i.a >= 1 and my_i.a <= 10) or (my_i.a >= 90 and my_i.a <= 100)))
            

    def disabled_test_array_compound(self):
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

            @vsc.dynamic_constraint
            def parent_c(self):
                self.c1[0].a[1].value == self.c2[0].x[1].value

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(5):    
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(5):    
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.dynamic_constraint
            def test_c(self):
                self.a[0].value == self.a[1].value

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

        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        inst=Parent()
        inst.randomize()
        with inst.randomize_with() as it:
            #it.parent_c()
            it.c1[0].test_c()
   
    
        print(inst.c1[0].a[1].value)
        print(inst.c2[0].x[1].value)
        print()
        print(inst.c1[0].a[0].value)
        print(inst.c1[0].a[1].value)         
             
        