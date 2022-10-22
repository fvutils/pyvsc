'''
Created on Jun 26, 2021

@author: mballance
'''
from enum import auto, Enum

from vsc_test_case import VscTestCase


class TestConstraintForeach(VscTestCase):
    
    def test_compound_array(self):
        import vsc 
        import random
        random.seed(0)

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
                self.x[0].value < self.x[1].value

        inst=Parent()
        inst.randomize(debug=0)
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)
        self.assertEqual(inst.c1[0].a[0].value, inst.c2[0].x[0].value)
        
    def test_compound_array_min(self):
        import vsc 
        import random
        random.seed(0)

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(2):
                    self.c1.append(vsc.attr(Child1()))

                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(2):
                    self.c2.append(vsc.attr(Child2()))

            @vsc.constraint
            def parent_c(self):
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
                for i in range(2):
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(2):
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.a[0].value < self.a[1].value
                pass

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
#                self.x[0].value < self.x[1].value
                pass

        inst=Parent()
        inst.randomize(debug=0)
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)
        self.assertEqual(inst.c1[0].a[0].value, inst.c2[0].x[0].value)        
        
        
    def test_nested_foreach(self):
        import vsc 
        import random
        # random.seed(3)
        
        level_list = [('level_'+str(level), auto()) for level in range(3)]
        level_e = Enum('level', dict(level_list))
        
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
        
                self.val = vsc.rand_uint16_t(5)
        
            @vsc.constraint
            def enum_inter_class(self):
                with vsc.foreach(self.c1, idx=True) as i:       
                    with vsc.foreach(self.c1[i].a, idx=True) as j:
                        with vsc.if_then(self.c1[i].a[0].enum_test == level_e.level_0):
                            self.c2[i].x[0].value == 0
                        
                        with vsc.else_if(self.c1[i].a[0].enum_test == level_e.level_1):
                            self.c2[i].x[0].value == 1
        
                        with vsc.else_then:
                            self.c2[i].x[0].value == 2
                
        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.enum_test = vsc.rand_enum_t(level_e)
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
        
                #self.enum_test = vsc.rand_enum_t(level_e)
        
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
                self.x[0].value < self.x[1].value
        
        inst=Parent()
        inst.randomize()
        
        for i in range(10):
            inst.randomize()
#            print("c1[0].a[0].enum_test=%s ; inst.c2[0].x[0].value=%d" % (
#                str(inst.c1[0].a[0].enum_test),
#                inst.c2[0].x[0].value))
            if inst.c1[0].a[0].enum_test == level_e.level_0:
                self.assertEqual(inst.c2[0].x[0].value, 0)
            elif inst.c1[0].a[0].enum_test == level_e.level_1:
                self.assertEqual(inst.c2[0].x[0].value, 1)
            else:
                self.assertEqual(inst.c2[0].x[0].value, 2)
                
            if inst.c1[1].a[0].enum_test == level_e.level_0:
                self.assertEqual(inst.c2[1].x[0].value, 0)
            elif inst.c1[1].a[0].enum_test == level_e.level_1:
                self.assertEqual(inst.c2[1].x[0].value, 1)
            else:
                self.assertEqual(inst.c2[1].x[0].value, 2)
                
#            print(inst.c1[0].a[0].enum_test)
#            print(inst.c2[0].x[0].value)
#            print()
#            print(inst.c1[1].a[0].enum_test)
#            print(inst.c2[1].x[0].value)
            #print(inst.val)
#            print()
        

    def test_foreach_access_bound_1(self):
        import vsc
        
        @vsc.randobj
        class Selector:
            def __init__(self):
                self.available = vsc.rangelist((0,19), (30,49))
                self.selectedList = vsc.rand_list_t(vsc.rand_uint16_t(), 5)
        
            @vsc.constraint
            def select_c(self):
                with vsc.foreach(self.selectedList, idx=True) as i:
                    self.selectedList[i].inside(self.available)
                    with vsc.if_then(i < 4):
                        self.selectedList[i] + 1 == self.selectedList[i+1]
        
        selector = Selector()
        selector.randomize()
        outStr = "selector.selectedList:"
        for sel in selector.selectedList:
            outStr += "\t" + str(int(sel))
        print(outStr)

    def test_mem_segments_1(self):
        import vsc

        @vsc.randobj
        class mem_segment(object):
            def __init__(self):
                self.capacity = vsc.rand_uint16_t()

        @vsc.randobj
        class mem_segments(object):

            def __init__(self):
                self.max_total_capacity = vsc.rand_uint16_t()
                self.mem_segments = vsc.rand_list_t(mem_segment())
                for _ in range(10):
                    self.mem_segments.append(mem_segment())
                self.sz_array = vsc.rand_list_t(vsc.rand_uint16_t(), 10)

            @vsc.constraint
            def sz_c(self):
                self.max_total_capacity >= 100
                self.max_total_capacity <= 200

                with vsc.foreach(self.mem_segments, idx=True, it=False) as idx:
                    self.sz_array[idx] == self.mem_segments[idx].capacity
                    self.mem_segments[idx].capacity <= self.max_total_capacity
                self.sz_array.sum == self.max_total_capacity

        ms = mem_segments()

        for _ in range(4):
            ms.randomize()
            print("max_total_capacity: %d" % ms.max_total_capacity)
            for i,s in enumerate(ms.mem_segments):
                print("[%d] %d" % (i, s.capacity))

    def test_mem_segments(self):
        import vsc

        @vsc.randobj
        class mem_segment(object):
            def __init__(self):
                self.capacity = vsc.rand_uint16_t()

        @vsc.randobj
        class mem_segments(object):

            def __init__(self):
                self.max_total_capacity = vsc.rand_uint16_t()
                self.mem_segments = vsc.rand_list_t(mem_segment())
                for _ in range(10):
                    self.mem_segments.append(mem_segment())
                self.sz_array = vsc.rand_list_t(vsc.rand_uint16_t(), 10)

            @vsc.constraint
            def sz_c(self):
                self.max_total_capacity >= 100
                self.max_total_capacity <= 200

                with vsc.foreach(self.mem_segments, idx=True, it=False) as idx:
                    self.sz_array[idx] == self.mem_segments[idx].capacity
                    self.mem_segments[idx].capacity <= self.max_total_capacity
                    with vsc.if_then(idx > 0):
                        with vsc.implies(self.mem_segments[idx].capacity > 0):
                            self.mem_segments[idx-1].capacity > 0
                
                self.sz_array.sum == self.max_total_capacity

        ms = mem_segments()
        ms.randomize()

        print("max_total_capacity: %d" % ms.max_total_capacity)
        for i,s in enumerate(ms.mem_segments):
            print("[%d] %d" % (i, s.capacity))



        