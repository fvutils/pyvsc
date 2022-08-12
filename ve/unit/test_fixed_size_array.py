'''
Created on Mar 4, 2020

@author: ballance
'''

from unittest import TestCase
import vsc
from .vsc_test_case import VscTestCase

class TestFixedSizeArray(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.my_arr = vsc.rand_list_t(vsc.uint8_t(), 16)
               
    def test_nested_foreach(self):
        @vsc.randobj
        class elem_c(object):
            
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.bit_t(4), sz=16)
                
            @vsc.constraint
            def unique_c(self):
#                with vsc.foreach(self.arr, idx=True) as i:
#                    self.arr[i] == i
                with vsc.foreach(self.arr, idx=True) as i:
                    with vsc.foreach(self.arr, idx=True) as j:
                        with vsc.implies(i != j):
                            self.arr[i] != self.arr[j]
                            
        it = elem_c()
        self.assertEqual(it.arr.size, 16)
        it.randomize()
        
        for i in range(it.arr.size):
            for j in range(it.arr.size):
                if i != j:
#                    print("[" + str(i) + "," + str(j) + "]  " + str(it.arr[i]) + "," + str(it.arr[j]))
                    self.assertNotEqual(it.arr[i], it.arr[j])
        
        

    def test_nested_array(self):
        
        @vsc.randobj
        class elem_c(object):
            
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.bit_t(4), sz=16)
                
            @vsc.constraint
            def unique_c(self):
#                with vsc.foreach(self.arr, idx=True) as i:
#                    self.arr[i] == i
                with vsc.foreach(self.arr, idx=True) as i:
                    with vsc.foreach(self.arr, idx=True) as j:
                        with vsc.implies(i != j):
                            self.arr[i] != self.arr[j]
                            
        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.arr = vsc.rand_list_t(elem_c(), sz=16)
#                self.elem = vsc.rand_attr(elem_c())
                
#                for i in range(16):
#                    self.arr.append(elem_c())
                    
        it = item_c()

        for i in range(1):
            it.randomize()
#            for v in it.elem.arr:
#                print("    " + str(v))
#            for elem in it.arr:
#                print("Array")
#                for v in elem.arr:
#                    print("    " + str(v))

    def test_array_fixedsz_sum(self):
        
        @vsc.randobj
        class item_c(object):
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.bit_t(8), sz=16)
                
            @vsc.constraint
            def elem_ne_c(self):
                with vsc.foreach(self.arr) as v:
                    v != 0
                
        it = item_c()

        for i in range(1):        
            with it.randomize_with():
                it.arr.sum > 0 
                it.arr.sum < 40

                with vsc.foreach(it.arr) as v:
                    v != 0

            for j in range(len(it.arr)):
                print("arr[" + str(j) + "] " + str(it.arr[j]))
                
            print("sum: " + str(it.arr.sum))
            self.assertGreater(it.arr.sum, 0)
            self.assertLess(it.arr.sum, 40)
            
    def test_array_fixedsz_product(self):
        
        @vsc.randobj
        class item_c(object):
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.bit_t(8), sz=8)
                
            @vsc.constraint
            def elem_ne_c(self):
                with vsc.foreach(self.arr) as v:
                    v != 0
                
        it = item_c()

        for i in range(1):        
            with it.randomize_with():
                it.arr.product == 4


            for j in range(len(it.arr)):
                print("arr[" + str(j) + "] " + str(it.arr[j]))
                
            print("product: " + str(it.arr.product))
            self.assertEqual(it.arr.product, 4)
            
    def test_array_sum(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.main_program = vsc.rand_uint8_t()
                self.total = vsc.rand_uint8_t()
                self.sub_program = vsc.rand_list_t(vsc.uint8_t(), sz=10)

            @vsc.constraint
            def ab_c(self):
                self.total == 50
                with vsc.foreach(self.sub_program) as it:
                    it != 0
                self.main_program + self.sub_program.sum == self.total

        my = my_s()

        # Randomize
        for i in range(5):
            my.randomize()
            print("MY ITEM : ",i+1)
            print(my.main_program , list(my.sub_program))        

    def test_sized_array(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                super().__init__()
                self.num_of_nested_loop = vsc.rand_bit_t(8)
                self.loop_init_val = vsc.randsz_list_t(vsc.uint8_t())
    

            @vsc.constraint
            def ab_con(self):
                self.num_of_nested_loop.inside(vsc.rangelist(1,2))
                self.loop_init_val.size.inside(vsc.rangelist(1,2))
                self.loop_init_val.size == self.num_of_nested_loop;


        item = my_s()

        for i in range(20):
            item.randomize()
            print("A = ",item.num_of_nested_loop,", B = ",item.loop_init_val)        

    def test_inline_foreach(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                super().__init__()
                self.arr = vsc.rand_list_t(vsc.uint8_t(), sz=10)
    
        item = my_s()
        
        with item.randomize_with() as it:
            with vsc.foreach(it.arr, idx=True) as i:
                with vsc.if_then(i == 0):
                    it.arr[i] == 1
                with vsc.else_then:
                    it.arr[i] == it.arr[i-1]+1

        for i in range(10):
            self.assertEqual(item.arr[i], i+1)


    def test_1(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.a_list = vsc.rand_list_t(vsc.uint8_t(),7)
                self.temp_list = vsc.rand_list_t(vsc.uint8_t(),7)
                self.c = 0
    
            @vsc.constraint
            def ab_c(self):
                with vsc.foreach(self.a_list, idx=True) as i:
                    if self.c:
                        self.a_list[i] in vsc.rangelist(5,6,7,8)
                    else:
                        self.a_list[i] in vsc.rangelist(10,11,12,13)

                with vsc.foreach(self.temp_list, idx=True) as i:
                    with vsc.if_then(self.a_list[i].inside(vsc.rangelist(6,7))):
                        self.temp_list[i] == 0
                    with vsc.else_then: 
                        self.temp_list[i] == 1

        my = my_s()
        my.randomize(debug=0)
        
        for v in my.a_list:
            self.assertIn(v, [10,11,12,13])
        for v in my.temp_list:
            self.assertEqual(v, 1)
        
    def disabled_test_2(self):
        @vsc.randobj
        class my_s(object):
            def __init__(self):
                self.a_list = vsc.rand_list_t(vsc.uint8_t(),7)
                self.temp_list = vsc.rand_list_t(vsc.uint8_t(),7)
                self.c = 0
    
            @vsc.constraint
            def ab_c(self):
                with vsc.foreach(self.a_list, idx=True) as i:
                    if self.c:
                        self.a_list[i] in vsc.rangelist(5,6,7,8)
                    else:
                        self.a_list[i] in vsc.rangelist(10,11,12,13)

                with vsc.foreach(self.temp_list, idx=True) as i:
                    if self.a_list[i] in [6,7]:
                        self.temp_list[i] == 0
                    else: 
                        self.temp_list[i] == 1

        my = my_s()
        my.randomize()
        
    def test_unique_unit_size_array(self):
        import vsc
        
        @vsc.randobj
        class Selector:
            def __init__(self):
                self.selectedList = vsc.rand_list_t(vsc.uint16_t(), 3)
        
            @vsc.constraint
            def list_c(self):
                vsc.unique(self.selectedList)
        
        selector = Selector()
        selector.selectedList.clear()
        selector.selectedList.extend([0, 0, 0])
        selector.randomize()         # 3-item list passes randomization.
        print(f"Selected List:  {selector.selectedList}")
        selector.selectedList.clear()
        selector.selectedList.extend([0, 0])
        selector.randomize()         # 2-item list passes randomization.
        print(f"Selected List:  {selector.selectedList}")
        selector.selectedList.clear()
        selector.selectedList.extend([0])
        selector.randomize()         # 1-item list throws BoolectorException.
        print(f"Selected List:  {selector.selectedList}")        
        
        
        