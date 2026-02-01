'''
Created on 2026-01-15

Test for rangelist tuple syntax bug with unsolvable constraints
'''
import unittest
from vsc_test_case import VscTestCase
import vsc

class TestConstraintRangelistBug(VscTestCase):
    
    def test_rangelist_tuple_syntax_with_unsolvable_constraints(self):
        """Test that tuple syntax in rangelist raises SolveFailure, not IndexError"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 128  
          
        # Case 1: Tuple syntax - should throw SolveFailure (currently throws IndexError - BUG)
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist((0, 50))
        
    def test_rangelist_multiarg_syntax_with_unsolvable_constraints(self):
        """Test that multi-arg syntax in rangelist correctly raises SolveFailure"""
        
        @vsc.randobj  
        class C():  
            def __init__(self):  
                self.a = vsc.rand_uint8_t()  
              
            @vsc.constraint  
            def constr(self):  
                self.a > 128  
          
        # Case 2: Multi-argument syntax - correctly throws SolveFailure  
        c = C()  
        with self.assertRaises(vsc.SolveFailure):
            with c.randomize_with() as it:  
                it.a in vsc.rangelist(0, 50)
