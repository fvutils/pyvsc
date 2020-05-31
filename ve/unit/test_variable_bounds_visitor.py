'''
Created on May 24, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc.visitors.variable_bound_visitor import VariableBoundVisitor

class TestVariableBoundsVisitor(VscTestCase):
    
    def test_smoke(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint16_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a < 10
                self.b < 4
                
        my_item = my_c()
        model = my_item.get_model()
        
        visitor = VariableBoundVisitor()
        visitor.process([model], [])
        
        a_model = model.find_field("a")
        b_model = model.find_field("b")
        
        self.assertIsNotNone(a_model)
        self.assertIsNotNone(b_model)

        self.assertTrue(a_model in visitor.bound_m.keys())
        self.assertTrue(b_model in visitor.bound_m.keys())
        
        a_bounds = visitor.bound_m[a_model]
        b_bounds = visitor.bound_m[b_model]
        
        self.assertEqual(1, len(a_bounds.domain.range_l))
        self.assertEqual(1, len(b_bounds.domain.range_l))

        # a in [0..9]        
        self.assertEqual(0, a_bounds.domain.range_l[0][0])
        self.assertEqual(9, a_bounds.domain.range_l[0][1])
        
        # b in [0..9]        
        self.assertEqual(0, b_bounds.domain.range_l[0][0])
        self.assertEqual(3, b_bounds.domain.range_l[0][1])

    def test_in(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint16_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a in vsc.rangelist(1, 4, 8)
                self.b in vsc.rangelist([2,4], [8,12])
                
        my_item = my_c()
        model = my_item.get_model()
        
        visitor = VariableBoundVisitor()
        visitor.process([model], [])
        
        a_model = model.find_field("a")
        b_model = model.find_field("b")
        
        self.assertIsNotNone(a_model)
        self.assertIsNotNone(b_model)

        self.assertTrue(a_model in visitor.bound_m.keys())
        self.assertTrue(b_model in visitor.bound_m.keys())
        
        a_bounds = visitor.bound_m[a_model]
        b_bounds = visitor.bound_m[b_model]

        self.assertEqual(3, len(a_bounds.domain.range_l))
        self.assertEqual(2, len(b_bounds.domain.range_l))

        # a in 1, 4, 8
        self.assertEqual(1, a_bounds.domain.range_l[0][0])
        self.assertEqual(1, a_bounds.domain.range_l[0][1])
        self.assertEqual(4, a_bounds.domain.range_l[1][0])
        self.assertEqual(4, a_bounds.domain.range_l[1][1])
        self.assertEqual(8, a_bounds.domain.range_l[2][0])
        self.assertEqual(8, a_bounds.domain.range_l[2][1])
        
        # b in [2..4] [8..12]
        self.assertEqual(2, b_bounds.domain.range_l[0][0])
        self.assertEqual(4, b_bounds.domain.range_l[0][1])
        self.assertEqual(8, b_bounds.domain.range_l[1][0])
        self.assertEqual(12, b_bounds.domain.range_l[1][1])

    def test_in_lt_limited(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint16_t()
                self.c = vsc.rand_uint16_t()
                
            @vsc.constraint
            def ab_c(self):
                self.a < 8
                self.a in vsc.rangelist(1, 4, 8)
                self.b in vsc.rangelist([2,4], [8,12])
                self.b < 11
                self.c in vsc.rangelist([2,4], [8,12])
                self.c < 4
                
        my_item = my_c()
        model = my_item.get_model()
        
        visitor = VariableBoundVisitor()
        visitor.process([model], [])
        
        a_model = model.find_field("a")
        b_model = model.find_field("b")
        c_model = model.find_field("c")
        
        self.assertIsNotNone(a_model)
        self.assertIsNotNone(b_model)
        self.assertIsNotNone(c_model)

        self.assertTrue(a_model in visitor.bound_m.keys())
        self.assertTrue(b_model in visitor.bound_m.keys())
        self.assertTrue(c_model in visitor.bound_m.keys())
        
        a_bounds = visitor.bound_m[a_model]
        b_bounds = visitor.bound_m[b_model]
        c_bounds = visitor.bound_m[c_model]

        self.assertEqual(2, len(a_bounds.domain.range_l))
        self.assertEqual(2, len(b_bounds.domain.range_l))
        self.assertEqual(1, len(c_bounds.domain.range_l))

        # a in 1, 4, 8
        self.assertEqual(1, a_bounds.domain.range_l[0][0])
        self.assertEqual(1, a_bounds.domain.range_l[0][1])
        self.assertEqual(4, a_bounds.domain.range_l[1][0])
        self.assertEqual(4, a_bounds.domain.range_l[1][1])
        
        # b in [2..4] [8..12]
        self.assertEqual(2, b_bounds.domain.range_l[0][0])
        self.assertEqual(4, b_bounds.domain.range_l[0][1])
        self.assertEqual(8, b_bounds.domain.range_l[1][0])
        self.assertEqual(10, b_bounds.domain.range_l[1][1])
        
        self.assertEqual(2, c_bounds.domain.range_l[0][0])
        self.assertEqual(3, c_bounds.domain.range_l[0][1])
                