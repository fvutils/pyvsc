'''
Created on Jun 9, 2020

@author: ballance
'''
from enum import auto, Enum, IntEnum
import time

import vsc
from vsc.types import uint8_t
from vsc_test_case import VscTestCase
from vsc.methods import raw_mode


class TestScalarArray(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.rand_list_t(uint8_t(), 10)
                
            @vsc.constraint
            def my_l_c(self):
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                

    def test_randsize_1(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.randsz_list_t(uint8_t())
                
            @vsc.constraint
            def my_l_c(self):
                self.my_l.size == 10
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
            
            self.assertEqual(it.my_l.size, 10)
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                
            
    def test_randsize_2(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l = vsc.randsz_list_t(uint8_t())
                
            @vsc.constraint
            def my_l_c(self):
                self.my_l.size > 0
                self.my_l.size <= 4
                with vsc.foreach(self.my_l) as it:
                    it < 10
                    pass
                    
                
        it = my_item_c()

        size_hist = [0]*4
        hist = []
        for i in range(10):        
            hist.append([0]*10)
        
        for i in range(100):
            it.randomize()
            
            self.assertLessEqual(it.my_l.size, 4)

            size_hist[it.my_l.size-1] += 1           
        
            for i,e in enumerate(it.my_l):
                self.assertLess(e, 10)
                hist[i][e] += 1

        print("Size Hist: " + str(size_hist))
        for i in range(10):
            print("Hist[" + str(i) + "] " + str(hist[i]))                            
            
    def test_large_arrays(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_l_1 = vsc.rand_list_t(uint8_t(), 1000)
                self.my_l_2 = vsc.rand_list_t(uint8_t(), 1000)
                
            @vsc.constraint
            def my_l_c(self):
                with vsc.foreach(self.my_l_1) as it:
                    it < 10
                with vsc.foreach(self.my_l_2) as it:
                    it < 10
                    
        it = my_item_c()

        count = 4
        start_m = int(round(time.time() * 1000))
        for i in range(count):
            it.randomize()
            
            for i,e in enumerate(it.my_l_1):
                self.assertLess(e, 10)
            for i,e in enumerate(it.my_l_2):
                self.assertLess(e, 10)
                
        end_m = int(round(time.time() * 1000))
                
        delta_m = (end_m-start_m)
        count_per_s = (count*1000)/delta_m
        ms_per_i = (delta_m/count)
       
        print("Delta: " + str(delta_m)) 
        print("Items/s: " + str(count_per_s) + " Time/item (ms): " + str(ms_per_i))
        

    def test_compound_enum_array(self):
        import vsc 

        level_list = [('level_'+str(level), auto()) for level in range(3)]
        level_e = Enum('level', dict(level_list))

#        level_list = [('level_'+str(level), auto()) for level in range(3)]
#        level_e = IntEnum('level', dict(level_list))

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
                # Does not work
                self.c1[0].a[0].enum_test == level_e.level_1

                with vsc.if_then(self.c1[0].a[0].enum_test == level_e.level_0):
                    self.c2[0].x[0].value == 0
        
                with vsc.else_if(self.c1[0].a[0].enum_test == level_e.level_1):
                    self.c2[0].x[0].value == 1

                with vsc.else_then:
                    self.c2[0].x[0].value == 2
        
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
            self.assertEqual(inst.c1[0].a[0].enum_test, level_e.level_1)
            self.assertEqual(inst.c2[0].x[0].value, 1)

    def test_compound_enum_array_min(self):
        import vsc 

#        level_list = [('level_'+str(level), auto()) for level in range(3)]
#        level_e = Enum('level', dict(level_list))

        level_list = [('level_'+str(level), auto()) for level in range(3)]
        level_e = IntEnum('level', dict(level_list))
        level_list = [('level_'+str(level), auto()) for level in range(3)]
#         class level_e(Enum):
#             level_0 = 0
#             level_1 = 1
#             level_2 = 2

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

                self.val = vsc.rand_uint16_t(5)

            @vsc.constraint
            def enum_inter_class(self):
                # Does not work
                self.c1[0].a[0].enum_test == level_e.level_2

                with vsc.if_then(self.c1[0].a[0].enum_test == level_e.level_0):
                    self.c2[0].x[0].value == 1
                with vsc.else_if(self.c1[0].a[0].enum_test == level_e.level_1):
                    self.c2[0].x[0].value == 2
                with vsc.else_then:
                    self.c2[0].x[0].value == 3
        
        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.enum_test = vsc.rand_enum_t(level_e)
#                self.enum_test = vsc.rand_int32_t()
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

                #self.enum_test = vsc.rand_enum_t(level_e)

            @vsc.constraint
            def test_c(self):
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

        inst.randomize()
        self.assertEqual(inst.c1[0].a[0].enum_test, level_e.level_2)
        self.assertEqual(inst.c2[0].x[0].value, 3)

    def test_list_sum_eq_fp_literal(self):

        @vsc.randobj
        class ThreadGroupConstraintItem(object):

            def __init__(self, aThreadNum, aSharePercent):
                self.mThreadNum = aThreadNum
                self.mSharePercent = aSharePercent

                self.GroupList = vsc.rand_list_t(vsc.rand_uint16_t(), self.mThreadNum)
                self.GroupListScore = vsc.rand_list_t(vsc.rand_uint16_t(), self.mThreadNum)
                self.GroupListId = vsc.rand_list_t(vsc.rand_uint16_t(), self.mThreadNum)

            @vsc.constraint
            def basic_c(self):
#                self.GroupList.sum == int(self.mThreadNum * self.mSharePercent/100)
                self.GroupList.sum == self.mThreadNum * self.mSharePercent/100

        obj = ThreadGroupConstraintItem(8, 80)
        obj.randomize()
        self.assertEqual(obj.GroupList.sum, 6)
        print("GroupList.sum=%d eq=%f" % (obj.GroupList.sum, (obj.mThreadNum * obj.mSharePercent/100)))