
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from unittest.case import TestCase
from vsc.types import rand_uint16_t
from vsc.attrs import rand_attr, attr
import vsc
from vsc_test_case import VscTestCase
from vsc.methods import raw_mode


class TestCompoundObj(VscTestCase):
    
    def test_rand_compound(self):

        @vsc.randobj        
        class C1(object):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()

        @vsc.randobj                
        class C2(object):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = rand_attr(C1())
                
        c2 = C2()
        
        for i in range(10):
            c2.randomize()
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b))

    def disabled_test_rand_compound_nonrand(self):

        @vsc.randobj        
        class C1(object):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()
                
        @vsc.randobj
        class C2(object):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = attr(C1())
                
                @vsc.constraint
                def c1_c2_c(self):
                    self.c1.a == self.c2.a
                
        c2 = C2()
        
        for i in range(10):
            c2.c2.a = i
            print("c2.c2.a=" + str(c2.c2.a))
            c2.randomize()  
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b) + " c2.a=" + str(c2.c2.a))    
            self.assertEqual(c2.c1.a, i)
            
    def test_uvm_mem(self):
        @vsc.randobj
        class my_sub_s(object):
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()

        @vsc.randobj
        class my_item_c(object):
            def __init__(self):
                self.test = vsc.rand_uint32_t()
#                self.my_l = vsc.rand_list_t(my_sub_s())
                self.my_l = vsc.list_t(my_sub_s())

                for i in range(5):
                    inst = my_sub_s()
                    inst.a = i*10
                    inst.b = i*10 + 5
                    self.my_l.append(inst)

            @vsc.constraint
            def test_c(self):
                with vsc.foreach(self.my_l, it=True, idx=True) as (i,it):
                    self.test.not_inside(vsc.rangelist([it.a,it.b]))

        my_item = my_item_c()
        for i in range(len(my_item.my_l)):
            print(str(my_item.my_l[i].a) + "  " + str(my_item.my_l[i].b))

        for i in range(5):
            my_item.randomize()
            print(my_item.test)
            
    def test_cross_array_elem_constraints(self):
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
            def ab_c(self):
                self.c1[0].a < 6
                pass

        @vsc.randobj
        class Child1():
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
    
            @vsc.constraint
            def test_c(self):
                self.a < 3

        @vsc.randobj
        class Child2():
            def __init__(self):
                self.x = vsc.rand_uint8_t()
                self.y = vsc.rand_uint8_t()
    
            @vsc.constraint
            def test_c(self):
                self.x < 6

        inst=Parent()
        inst.randomize()
        print(inst.c1[0].a)
        print(inst.c2[1].x)
        
    def test_two_layer_small(self):
        
        @vsc.randobj
        class Top(object):
            def __init__(self):
                self.c1 = vsc.rand_list_t(vsc.attr(Sub1()))
                self.c1.append(vsc.attr(Sub1()))
                
            @vsc.constraint
            def array_c(self):
                self.c1[0].c2[0].a == 2
                
        @vsc.randobj
        class Sub1(object):
            
            def __init__(self):
                self.c2 = vsc.rand_list_t(vsc.attr(Sub2()))
                self.c2.append(vsc.attr(Sub2()))
                self.c3 = vsc.rand_list_t(vsc.attr(Sub2()))
                self.c3.append(vsc.attr(Sub2()))
                
        @vsc.randobj
        class Sub2(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
        t = Top()
                
    def test_one_layer_small(self):
        
        @vsc.randobj
        class Top(object):
            def __init__(self):
                s = Sub1()
                si = Sub1()
                print("--> c1.create")
                self.c1 = vsc.rand_list_t(vsc.attr(s))
                print("<-- c1.create")
                self.c1.append(vsc.attr(si))
                
            @vsc.constraint
            def array_c(self):
                self.c1[0].a == 2
                
        @vsc.randobj
        class Sub1(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                
        t = Top()
                
    def test_two_layer(self):
        import vsc 

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.rand_attr(Child1()))
                for i in range(2):    
                    self.c1.append(vsc.rand_attr(Child1()))      

                self.c2 = vsc.rand_list_t(vsc.rand_attr(Child2()))
                for i in range(2):
                    self.c2.append(vsc.rand_attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 
                pass
#                self.c1[0].a[1].value == 2

#                with vsc.foreach(self.c1, idx=True) as i:
#                    self.c1[i].a[0].value == self.c2[i].x[0].value


        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.rand_attr(Field('an', 10)))
                for i in range(2):    
                    self.a.append(vsc.rand_attr(Field('an', 10)))

                self.b = vsc.rand_list_t(vsc.rand_attr(Field('bn', 10)))
                for i in range(1):    
                    self.b.append(vsc.rand_attr(Field('bn', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.a[0].value < self.a[1].value
#                self.a[0].value == self.a[1].value
                pass

        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.rand_attr(Field('x', 10)))
                for i in range(2):
                    self.x.append(vsc.rand_attr(Field('x', 10)))

                self.y = vsc.rand_list_t(vsc.rand_attr(Field('y', 10)))
                for i in range(1):    
                    self.y.append(vsc.rand_attr(Field('y', 10)))
    
            @vsc.constraint
            def test_c(self):
                self.x[0].value < self.x[1].value
                pass

        inst=Parent()
        inst.randomize(debug=0)
       
        for i in range(inst.c2.size):
            print("c[%d].x[0].value=%d c2[%d].x[1].value=%d" % (
                i, inst.c2[i].x[0].value, i, inst.c2[i].x[1].value))
            with vsc.raw_mode():
                print("%s %s" % (
                    inst.c2[i].x[0].value.get_model().fullname, 
                    inst.c2[i].x[1].value.get_model().fullname))
        
        for i in range(inst.c2.size):
#            self.assertEqual(inst.c1[i].a[0].value, inst.c1[i].a[1].value)
            self.assertLess(inst.c2[i].x[0].value, inst.c2[i].x[1].value)
            
        print(inst.c1[0].a[0].value)
        print(inst.c1[0].a[1].value)
        print(inst.c2[0].x[0].value)        

    def test_two_layer_1(self):
        import vsc 

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.rand_attr(Child1()))
                for i in range(10):    
                    self.c1.append(vsc.rand_attr(Child1()))      

                self.c2 = vsc.rand_list_t(vsc.rand_attr(Child2()))
                for i in range(10):
                    self.c2.append(vsc.rand_attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                pass
                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 

#                with vsc.foreach(self.c1, idx=True) as i:
#                    self.c1[i].a[0].value == self.c2[i].x[0].value


        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.rand_attr(Field('an', 10)))
                for i in range(5):    
                    self.a.append(vsc.rand_attr(Field('an', 10)))

                self.b = vsc.rand_list_t(vsc.rand_attr(Field('bn', 10)))
                for i in range(5):    
                    self.b.append(vsc.rand_attr(Field('bn', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.a[0].value < self.a[1].value
#                self.a[0].value == self.a[1].value
                pass

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
                pass

        inst=Parent()
        inst.randomize(debug=0)
        self.assertEqual(
            inst.c1[0].a[1].value, 
            inst.c2[0].x[1].value)
            
        print(inst.c1[0].a[0].value)
        print(inst.c1[0].a[1].value)
        print(inst.c2[0].x[0].value)
        
    def test_two_layer_2(self):
        import vsc 

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.rand_attr(Child1()))
                for i in range(10):    
                    self.c1.append(vsc.rand_attr(Child1()))      

                self.c2 = vsc.rand_list_t(vsc.rand_attr(Child2()))
                for i in range(10):
                    self.c2.append(vsc.rand_attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                pass
#                self.c1[0].a[1].value == self.c2[0].x[1].value       # Multi-level 
                self.c1[0].a[1].value == self.c2[0].x[1].value

#                with vsc.foreach(self.c1, idx=True) as i:
#                    self.c1[i].a[0].value == self.c2[i].x[0].value


        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.rand_attr(Field('an', 10)))
                for i in range(5):    
                    self.a.append(vsc.rand_attr(Field('an', 10)))

                self.b = vsc.rand_list_t(vsc.rand_attr(Field('bn', 10)))
                for i in range(5):    
                    self.b.append(vsc.rand_attr(Field('bn', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.a[0].value < self.a[1].value
#                self.a[0].value == self.a[1].value
                pass

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
#                self.x[0].value < self.x[1].value
                pass

        inst=Parent()
        inst.randomize(debug=0)
        self.assertEqual(inst.c1[0].a[1].value, inst.c2[0].x[1].value)
            
        print(inst.c1[0].a[0].value)
        print(inst.c1[0].a[1].value)
        print(inst.c2[0].x[0].value)        
        
    def test_array_inst_constraint_mode(self):
        import vsc 
        
        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.rand_attr(Child1()))
                for i in range(3):    
                    self.c1.append(vsc.rand_attr(Child1()))

        @vsc.randobj
        class Child1():
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
    
            @vsc.constraint
            def test_c(self):
                self.a < 6
                self.b < 3
                self.a*self.b == 10

        inst=Parent()
        inst.c1[0].test_c.constraint_mode(False)
        with inst.randomize_with():
            inst.c1[0].a == 10
            inst.c1[0].b == 20
            pass

        self.assertEqual(inst.c1[0].a, 10)
        self.assertEqual(inst.c1[0].b, 20)
        self.assertLess(inst.c1[1].a, 6)
        self.assertLess(inst.c1[1].b, 3)
        print("inst.c1[0].a =", inst.c1[0].a)
        print("inst.c1[0].b =", inst.c1[0].b)
        print("inst.c1[2].a =", inst.c1[2].a)
        print("inst.c1[2].b =", inst.c1[2].b)        
        

    def test_orig(self):
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

                with vsc.foreach(self.c1, idx=True) as i:
                    self.c1[i].a[0].value == self.c2[i].x[0].value


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
    
            @vsc.constraint
            def test_c(self):
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
                pass
                self.x[0].value < self.x[1].value

        inst=Parent()
        inst.randomize(debug=0)
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)        

    def test_nested_objects(self):

        @vsc.randobj
        class Field(object):
            def __init__(self):
                self.c = vsc.rand_uint8_t()


        @vsc.randobj
        class Child(object):
            def __init__(self):
                self.b = vsc.rand_attr(Field())


        @vsc.randobj
        class Parent(object):
            def __init__(self):
                self.a = vsc.rand_list_t(Child(), 2)

            @vsc.constraint
            def eq_c(self):
                self.a[0].b.c == self.a[1].b.c


        item = Parent()
        item.randomize(debug=False)

    def test_nested_objects2(self):
        @vsc.randobj
        class Field(object):
            def __init__(self):
                self.d = vsc.rand_uint8_t()

        @vsc.randobj
        class Child1(object):
            def __init__(self):
                self.b = vsc.rand_list_t(Child2(), 2)

        @vsc.randobj
        class Child2(object):
            def __init__(self):
                self.c = vsc.rand_attr(Field())

        @vsc.randobj
        class Parent(object):
            def __init__(self):
                self.a = vsc.rand_list_t(Child1(), 2)

            @vsc.constraint
            def eq_c(self):
                self.a[0].b[0].c.d == self.a[1].b[0].c.d

        item = Parent()
        item.randomize()
        print(f"{item.a[0].b[0].c.d} {item.a[1].b[0].c.d}")

    def test_nested_objects3(self):
        @vsc.randobj
        class Item(object):
            def __init__(self):
                self.a = vsc.list_t(vsc.rand_list_t(vsc.rand_bit_t(2), 2))
                pass

        item = Item()
