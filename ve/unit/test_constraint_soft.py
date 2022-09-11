'''
Created on Mar 21, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestConstraintSoft(VscTestCase):
    
    def test_soft_smoke(self):
        
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_lt_b(self):
                vsc.soft(self.a < self.b)
                self.a > 0
                
        my_i = my_cls()
        
        with my_i.randomize_with() as i:
            i.a == i.b
            
        print("a=" + str(my_i.a) + " b=" + str(my_i.b))
            
        self.assertEqual(my_i.a, my_i.b)

        # Should be able to respect the soft constraints        
        with my_i.randomize_with() as i:
            i.a != i.b
            
        print("a=" + str(my_i.a) + " b=" + str(my_i.b))
            
        self.assertNotEqual(my_i.a, my_i.b)
        self.assertLess(my_i.a, my_i.b)
        self.assertGreater(my_i.a, 0)
        
    def test_soft_dist(self):
        
        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                self.a < self.b
                vsc.soft(self.a > 5) #A
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  10),
                    vsc.weight(1,  100),
                    vsc.weight(2,  10),
                    vsc.weight(4,  10),
                    vsc.weight(8, 10)])

        item = my_item()
        for i in range(10):
            with item.randomize_with(debug=0) as it:
                it.b > 10
                it.a == 1 #B

    def test_soft_dist_priority(self):
        """Ensures that dist constraints take priority over soft constraints"""
        
        @vsc.randobj
        class my_item(object):
            def __init__(self):
                self.a = vsc.rand_bit_t(8)
                self.b = vsc.rand_bit_t(8)

            @vsc.constraint
            def valid_ab_c(self):
                self.a < self.b
                vsc.soft(self.a > 5) #A
         
            @vsc.constraint
            def dist_a(self):
                vsc.dist(self.a, [
                    vsc.weight(0,  10),
                    vsc.weight(1,  10),
                    vsc.weight(2,  10),
                    vsc.weight(4,  10),
                    vsc.weight(8, 10)])

        hist = [0]*9
        item = my_item()
        for i in range(100):
            item.randomize()
            hist[item.a] += 1

        self.assertGreater(hist[0], 0) 
        self.assertGreater(hist[1], 0) 
        self.assertGreater(hist[2], 0) 
        self.assertGreater(hist[4], 0) 
        self.assertGreater(hist[8], 0) 

    def test_compound_array(self):
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

            @vsc.constraint
            def parent_c(self):
                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 
                pass

        @vsc.randobj
        class Field:
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

            # @vsc.constraint
            # def soft_t(self):
            #     #soft(self.value == 5)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(5):    
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(5):    
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.constraint
            def test_c(self):
                #self.a[0].value < 7                # Works
                vsc.soft(self.a[0].value == 5)          # Fails
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
        inst.randomize(debug=0)
        print("inst.c1[0].a[0].value", inst.c1[0].a[0].value)
        self.assertEqual(inst.c1[0].a[0].value, 5)
        print("inst.c1[0].a[1].value", inst.c1[0].a[1].value)
#        print()

#        print("inst.c2[0].x[0].value", inst.c2[0].x[0].value)
#        print("inst.c2[0].x[1].value", inst.c2[0].x[1].value)

    def test_compound_array_min(self):
        import vsc 
        
        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(1):    
                    self.c1.append(vsc.attr(Child1()))      

                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(1):
                    self.c2.append(vsc.attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 
                pass

        @vsc.randobj
        class Field:
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

            # @vsc.constraint
            # def soft_t(self):
            #     #soft(self.value == 5)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(2):
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(2):    
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.constraint
            def test_c(self):
                #self.a[0].value < 7                # Works
                vsc.soft(self.a[0].value == 5)          # Fails
                self.a[0].value < self.a[1].value   
        
        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.attr(Field('x', 10)))
                for i in range(2):
                    self.x.append(vsc.attr(Field('x', 10)))
 
                self.y = vsc.rand_list_t(vsc.attr(Field('y', 10)))
                for i in range(2):
                    self.y.append(vsc.attr(Field('y', 10)))
     
            @vsc.constraint
            def test_c(self):
                self.x[0].value < self.x[1].value

        inst=Parent()
        inst.randomize(debug=0)
        print("inst.c1[0].a[0].value", inst.c1[0].a[0].value)
        self.assertEqual(inst.c1[0].a[0].value, 5)
        print("inst.c1[0].a[1].value", inst.c1[0].a[1].value)
#        print()

#        print("inst.c2[0].x[0].value", inst.c2[0].x[0].value)
#        print("inst.c2[0].x[1].value", inst.c2[0].x[1].value)

    def test_soft_dynamic(self):
        @vsc.randobj
        class RandA:
            def __init__(self):
                self.a_field = vsc.rand_uint8_t(8)
                self.b_field = vsc.rand_uint8_t(8)

            @vsc.constraint
            def default_c(self):
                self.a_field < 100
                self.b_field < 200
                pass

    
            @vsc.dynamic_constraint
            def fixed_c(self):
                vsc.soft(self.a_field == 8)
                vsc.soft(self.b_field == 8)

        rand_a = RandA()

        with rand_a.randomize_with(solve_fail_debug=1,debug=1) as it:
            it.fixed_c()
            it.a_field == 10

        print(rand_a.a_field)
        pass
        