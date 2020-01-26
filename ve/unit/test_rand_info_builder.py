'''
Created on Jan 22, 2020

@author: ballance
'''
from unittest.case import TestCase
from vsc.rand_obj import RandObj
from vsc.types import rand_bit_t
from vsc.model.rand_info_builder import RandInfoBuilder
import vsc

class TestRandInfoBuilder(TestCase):
    
    def test_no_refs(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 0)
        self.assertEqual(len(info.unconstrained_l), 2)
        
    def test_single_var_ref(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < 5
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 1)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 1)
        
    def test_multi_indep_var_ref(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < 5
                self.b ==  5
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 2)
        self.assertEqual(len(info.randset_l[0].fields()), 1)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.randset_l[1].fields()), 1)
        self.assertEqual(len(info.randset_l[1].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)
        
    def test_multi_dep_var_ref(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 2)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)

    def test_two_randsets(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                self.c = rand_bit_t(8)
                self.d = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                self.c < self.d
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 2)
        self.assertEqual(len(info.randset_l[0].fields()), 2)
        self.assertEqual(len(info.randset_l[0].constraints()), 1)
        self.assertEqual(len(info.randset_l[1].fields()), 2)
        self.assertEqual(len(info.randset_l[1].constraints()), 1)
        self.assertEqual(len(info.unconstrained_l), 0)        

    def test_connected_top_level(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                self.c = rand_bit_t(8)
                self.d = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                self.b < self.c
                self.c < self.d
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 3)
        self.assertEqual(len(info.unconstrained_l), 0)        

    def test_connected_ite_cond(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                self.c = rand_bit_t(8)
                self.d = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                with vsc.if_then (self.b < self.c):
                    self.c < self.d
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.unconstrained_l), 0)

    def test_connected_ite_cross_block(self):
        
        class my_cls(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_bit_t(8)
                self.b = rand_bit_t(8)
                self.c = rand_bit_t(8)
                self.d = rand_bit_t(8)
                
            @vsc.constraint
            def a_c(self):
                self.a < self.b
                    
            @vsc.constraint
            def b_c(self):
                with vsc.if_then (self.b < self.c):
                    self.c < self.d
                
        my_cls_i = my_cls()
        
        info = RandInfoBuilder.build([my_cls_i.get_model()], [])
        self.assertEqual(len(info.randset_l), 1)
        self.assertEqual(len(info.randset_l[0].fields()), 4)
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.unconstrained_l), 0)        
        
