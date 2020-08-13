'''
Created on Mar 4, 2020

@author: ballance
'''

from unittest import TestCase
import vsc
from vsc_test_case import VscTestCase

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
        
        for i in range(it.arr.size):
            for j in range(it.arr.size):
                if i != j:
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
        
        
