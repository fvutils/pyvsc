'''
Created on 2026-02-03

Extended test cases for rangelist constraints with unsolvable scenarios
Tests various edge cases to ensure robust error handling
'''
import unittest
from vsc_test_case import VscTestCase
import vsc

class TestConstraintRangelistExtended(VscTestCase):
    
    def test_rangelist_tuple_empty_domain(self):
        """Test tuple syntax with completely empty domain after constraint propagation"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 255  # Impossible for uint8_t
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((0, 10))
    
    def test_rangelist_multiple_tuples_unsolvable(self):
        """Test multiple tuple ranges with unsolvable constraints"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 200  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((0, 50), (51, 100), (101, 150))
    
    def test_rangelist_single_value_tuple_unsolvable(self):
        """Test single value tuple (range of one) with unsolvable constraint"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 100  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((50, 50))
    
    def test_rangelist_boundary_tuple_unsolvable(self):
        """Test boundary conditions with tuple syntax"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a < 10  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((200, 255))
    
    def test_rangelist_mixed_syntax_unsolvable(self):
        """Test mixed tuple and range syntax with unsolvable constraints"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 150  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((0, 50), 75, (100, 120))
    
    def test_rangelist_tuple_overlapping_with_constraint(self):
        """Test tuple syntax where constraint narrows to empty set"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 100
                self.a < 90  # Impossible: a cannot be both > 100 and < 90
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_rangelist_tuple_zero_based_range_unsolvable(self):
        """Test tuple with zero-based range and unsolvable constraint"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 100  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((0, 0))
    
    def test_rangelist_tuple_max_value_unsolvable(self):
        """Test tuple with maximum value and unsolvable constraint"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a < 128  
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((255, 255))
    
    def test_rangelist_tuple_success_case(self):
        """Verify tuple syntax works correctly when constraints are solvable"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 100  
          
        c = C()  
        # This should succeed
        with c.randomize_with() as it:  
            it.a in vsc.rangelist((120, 150))
        
        # Verify the value is within the expected range
        self.assertGreaterEqual(c.a, 120)
        self.assertLessEqual(c.a, 150)
        self.assertGreater(c.a, 100)
    
    def test_rangelist_multiarg_empty_domain(self):
        """Test multi-arg syntax with completely empty domain (baseline)"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 255  # Impossible for uint8_t
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist(0, 10)
