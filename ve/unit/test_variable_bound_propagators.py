'''
Created on 2026-02-03

Test cases for variable bound propagators with empty domains
Tests to catch IndexError in bounds propagators
'''
import unittest
from vsc_test_case import VscTestCase
import vsc

class TestVariableBoundPropagators(VscTestCase):
    
    def test_bounds_max_propagator_with_empty_domain(self):
        """Test that bounds max propagator handles empty domains correctly"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                # Create a scenario where b's domain becomes empty
                # and b is used to set bounds on a
                self.b < self.a
                self.a < 10
                self.b > 250  # Impossible: b > 250 and b < a < 10
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_bounds_min_propagator_with_empty_domain(self):
        """Test that bounds min propagator handles empty domains correctly"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                # Create a scenario where b's domain becomes empty
                # and b is used to set minimum bounds on a
                self.a > self.b
                self.b > 200
                self.b < 10  # Impossible: b > 200 and b < 10
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_chained_bounds_propagators_empty_domain(self):
        """Test chained bounds propagators with empty intermediate domain"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                # Chain: a < b < c, but make b's domain empty
                self.a < self.b
                self.b < self.c
                self.b > 200
                self.b < 50  # Impossible for b
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_variable_comparison_with_rangelist_empty_domain(self):
        """Test variable comparison combined with rangelist causing empty domain"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                self.a > self.b
                self.b > 128
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:
                # This combined with b > 128 and a > b makes a's valid range very limited
                # Then the rangelist makes it impossible
                it.a in vsc.rangelist((0, 50))
    
    def test_multiple_variable_bounds_empty_domain(self):
        """Test multiple variable bounds creating empty domain"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                # Create circular-like impossible constraints
                self.a < self.b
                self.b < self.c
                self.c < self.a  # Impossible: a < b < c < a
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_bounds_with_offset_empty_domain(self):
        """Test bounds propagators with offset causing empty domain"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                # a must equal b + 50, but both constrained to small range
                self.a == self.b + 50
                self.a < 30  # a must be < 30
                self.b > 100  # b must be > 100, so a must be > 150
          
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            c.randomize()
    
    def test_variable_bounds_success_case(self):
        """Verify variable bounds work correctly when constraints are solvable"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
              
            @vsc.constraint  
            def constr(self):  
                self.a > self.b
                self.b > 50
                self.b < 100
          
        c = C()
        # This should succeed
        c.randomize()
        
        # Verify the constraints are satisfied
        self.assertGreater(c.a, c.b)
        self.assertGreater(c.b, 50)
        self.assertLess(c.b, 100)
