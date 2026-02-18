'''
Created on Feb 1, 2026

@author: copilot

Tests for arithmetic operators in coverpoint expressions
'''
from vsc_test_case import VscTestCase
import vsc

class TestCoverpointArithmeticOperators(VscTestCase):
    
    def test_coverpoint_multiplication(self):
        """Test multiplication operator in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.prod_cp = vsc.coverpoint(self.a * self.b, bins={
                    "prod": vsc.bin_array([], 1, 2, 4, 12)
                })
        
        cg = my_covergroup()
        cg.sample(2, 6)  # 2 * 6 = 12
        cg.sample(1, 1)  # 1 * 1 = 1
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_division(self):
        """Test division operators in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.div_cp = vsc.coverpoint(self.a / self.b, bins={
                    "div": vsc.bin_array([], 1, 2, 4, 8)
                })
        
        cg = my_covergroup()
        cg.sample(8, 4)  # 8 / 4 = 2
        cg.sample(8, 1)  # 8 / 1 = 8
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_floordiv(self):
        """Test floor division operator in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.div_cp = vsc.coverpoint(self.a // self.b, bins={
                    "div": vsc.bin_array([], 1, 2, 4, 8)
                })
        
        cg = my_covergroup()
        cg.sample(9, 4)  # 9 // 4 = 2
        cg.sample(8, 1)  # 8 // 1 = 8
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_modulo(self):
        """Test modulo operator in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.mod_cp = vsc.coverpoint(self.a % self.b, bins={
                    "mod": vsc.bin_array([], 0, 1, 2, 3)
                })
        
        cg = my_covergroup()
        cg.sample(10, 3)  # 10 % 3 = 1
        cg.sample(11, 3)  # 11 % 3 = 2
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_reverse_add(self):
        """Test reverse add operator (constant on left) in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.sum_cp = vsc.coverpoint(1 + self.a + self.b, bins={
                    "sum" : vsc.bin_array([], 1, 3, 5, 9)
                })
        
        cg = my_covergroup()
        cg.sample(2, 6)  # 1 + 2 + 6 = 9
        cg.sample(1, 1)  # 1 + 1 + 1 = 3
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_reverse_multiply(self):
        """Test reverse multiply operator (constant on left)"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t()
                ))
                
                self.prod_cp = vsc.coverpoint(2 * self.a, bins={
                    "prod": vsc.bin_array([], 2, 4, 8, 16)
                })
        
        cg = my_covergroup()
        cg.sample(2)  # 2 * 2 = 4
        cg.sample(8)  # 2 * 8 = 16
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_reverse_subtract(self):
        """Test reverse subtract operator (constant on left)"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t()
                ))
                
                self.diff_cp = vsc.coverpoint(10 - self.a, bins={
                    "diff": vsc.bin_array([], 2, 4, 6, 8)
                })
        
        cg = my_covergroup()
        cg.sample(2)  # 10 - 2 = 8
        cg.sample(6)  # 10 - 6 = 4
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_reverse_divide(self):
        """Test reverse divide operator (constant on left)"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t()
                ))
                
                self.div_cp = vsc.coverpoint(100 / self.a, bins={
                    "div": vsc.bin_array([], 10, 20, 25, 50)
                })
        
        cg = my_covergroup()
        cg.sample(5)  # 100 / 5 = 20
        cg.sample(4)  # 100 / 4 = 25
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_complex_expression(self):
        """Test complex arithmetic expression in coverpoint"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t(),
                    c = vsc.uint8_t()
                ))
                
                # Complex expression: (a * b) + (c / 2)
                self.complex_cp = vsc.coverpoint((self.a * self.b) + (self.c // 2), bins={
                    "result": vsc.bin_array([], 5, 10, 15, 20)
                })
        
        cg = my_covergroup()
        cg.sample(2, 5, 4)  # (2 * 5) + (4 // 2) = 10 + 2 = 12 (should hit bin 10)
        cg.sample(3, 5, 10) # (3 * 5) + (10 // 2) = 15 + 5 = 20
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_bitwise_operations(self):
        """Test bitwise operations in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.or_cp = vsc.coverpoint(self.a | self.b, bins={
                    "or": vsc.bin_array([], 1, 3, 7, 15)
                })
                
                self.xor_cp = vsc.coverpoint(self.a ^ self.b, bins={
                    "xor": vsc.bin_array([], 0, 1, 2, 4)
                })
        
        cg = my_covergroup()
        cg.sample(5, 3)  # 5 | 3 = 7, 5 ^ 3 = 6
        cg.sample(1, 0)  # 1 | 0 = 1, 1 ^ 0 = 1
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_coverpoint_shift_operations(self):
        """Test shift operations in coverpoint expressions"""
        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                self.lshift_cp = vsc.coverpoint(self.a << self.b, bins={
                    "lshift": vsc.bin_array([], 2, 4, 8, 16)
                })
                
                self.rshift_cp = vsc.coverpoint(self.a >> self.b, bins={
                    "rshift": vsc.bin_array([], 1, 2, 4, 8)
                })
        
        cg = my_covergroup()
        cg.sample(2, 2)  # 2 << 2 = 8, 2 >> 2 = 0
        cg.sample(16, 1) # 16 << 1 = 32, 16 >> 1 = 8
        
        # Verify coverage was recorded
        self.assertGreater(cg.get_coverage(), 0.0)
    
    def test_original_issue_example(self):
        """Test the exact example from the issue report"""
        @vsc.covergroup
        class my_covergroup():
            def __init__(self):
                self.with_sample(dict(
                    a = vsc.uint8_t(),
                    b = vsc.uint8_t()
                ))
                
                # Case 1: Constant on left (Reverse Add)
                self.sum_cp = vsc.coverpoint(1 + self.a + self.b, bins={
                    "sum" : vsc.bin_array([], 1, 2, 4, 8)
                })
                
                # Case 2: Multiplication
                self.prod_cp = vsc.coverpoint(self.a * self.b, bins={
                    "prod": vsc.bin_array([], 1, 2, 4, 12)
                })
        
        cg = my_covergroup()
        cg.sample(2, 6)
        
        # Verify coverage was recorded without exception
        self.assertGreater(cg.get_coverage(), 0.0)
