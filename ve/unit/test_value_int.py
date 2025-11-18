'''
Created on Nov 8, 2024

Test for ValueInt.from_bits functionality
'''
import sys
import os
# Add src to path to allow importing vsc modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from unittest import TestCase

# Import ValueInt directly to avoid full vsc package dependencies
try:
    from vsc.types import ValueInt
except ImportError:
    # Fallback to direct import if vsc package can't be fully loaded
    from vsc.model.value_scalar import ValueInt


class TestValueInt(TestCase):
    
    def test_from_bits_unsigned_8bit(self):
        """Test unsigned 8-bit value conversion"""
        # Test maximum unsigned value
        result = ValueInt.from_bits(0xFF, 8, signed=False)
        self.assertEqual(result, 255)
        
        # Test zero
        result = ValueInt.from_bits(0x00, 8, signed=False)
        self.assertEqual(result, 0)
        
        # Test mid-range value
        result = ValueInt.from_bits(0x7F, 8, signed=False)
        self.assertEqual(result, 127)
        
    def test_from_bits_signed_8bit(self):
        """Test signed 8-bit value conversion"""
        # Test -1 (0xFF in 8-bit two's complement)
        result = ValueInt.from_bits(0xFF, 8, signed=True)
        self.assertEqual(result, -1)
        
        # Test -128 (0x80 in 8-bit two's complement)
        result = ValueInt.from_bits(0x80, 8, signed=True)
        self.assertEqual(result, -128)
        
        # Test positive value (MSB = 0)
        result = ValueInt.from_bits(0x7F, 8, signed=True)
        self.assertEqual(result, 127)
        
        # Test zero
        result = ValueInt.from_bits(0x00, 8, signed=True)
        self.assertEqual(result, 0)
        
    def test_from_bits_unsigned_32bit(self):
        """Test unsigned 32-bit value conversion"""
        # Test maximum unsigned 32-bit value
        result = ValueInt.from_bits(0xFFFFFFFF, 32, signed=False)
        self.assertEqual(result, 4294967295)
        
        # Test mid-range value
        result = ValueInt.from_bits(0x80000000, 32, signed=False)
        self.assertEqual(result, 2147483648)
        
    def test_from_bits_signed_32bit(self):
        """Test signed 32-bit value conversion"""
        # Test -1 (0xFFFFFFFF in 32-bit two's complement)
        result = ValueInt.from_bits(0xFFFFFFFF, 32, signed=True)
        self.assertEqual(result, -1)
        
        # Test minimum signed 32-bit value
        result = ValueInt.from_bits(0x80000000, 32, signed=True)
        self.assertEqual(result, -2147483648)
        
        # Test positive value
        result = ValueInt.from_bits(0x7FFFFFFF, 32, signed=True)
        self.assertEqual(result, 2147483647)
        
    def test_from_bits_masking(self):
        """Test that values are properly masked to specified width"""
        # Value larger than 8 bits should be masked
        result = ValueInt.from_bits(0x1FF, 8, signed=False)
        self.assertEqual(result, 0xFF)
        
        # Value larger than 4 bits should be masked
        result = ValueInt.from_bits(0xFF, 4, signed=False)
        self.assertEqual(result, 0x0F)
        
        # Signed masking
        result = ValueInt.from_bits(0xFF, 4, signed=True)
        self.assertEqual(result, -1)
        
    def test_from_bits_sign_detection(self):
        """Test sign bit detection at various widths"""
        # 4-bit: 0x8 should be -8 when signed
        result = ValueInt.from_bits(0x8, 4, signed=True)
        self.assertEqual(result, -8)
        
        # 4-bit: 0x7 should be 7 when signed (positive)
        result = ValueInt.from_bits(0x7, 4, signed=True)
        self.assertEqual(result, 7)
        
        # 16-bit: 0x8000 should be -32768 when signed
        result = ValueInt.from_bits(0x8000, 16, signed=True)
        self.assertEqual(result, -32768)
        
        # 16-bit: 0x7FFF should be 32767 when signed (positive)
        result = ValueInt.from_bits(0x7FFF, 16, signed=True)
        self.assertEqual(result, 32767)
        
    def test_from_bits_edge_cases(self):
        """Test edge cases"""
        # 1-bit unsigned
        result = ValueInt.from_bits(1, 1, signed=False)
        self.assertEqual(result, 1)
        
        result = ValueInt.from_bits(0, 1, signed=False)
        self.assertEqual(result, 0)
        
        # 1-bit signed: can only represent -1 and 0
        result = ValueInt.from_bits(1, 1, signed=True)
        self.assertEqual(result, -1)
        
        result = ValueInt.from_bits(0, 1, signed=True)
        self.assertEqual(result, 0)
        
    def test_from_bits_practical_dut_example(self):
        """Test practical example from DUT interface"""
        # Simulating a DUT returning 0xFFFFFFF0 from a 32-bit signed register
        dut_val = 0xFFFFFFF0
        vsc_val = ValueInt.from_bits(dut_val, width=32, signed=True)
        self.assertEqual(vsc_val, -16)
        
        # Simulating a DUT returning 0xFF from an 8-bit signed register
        dut_val = 0xFF
        vsc_val = ValueInt.from_bits(dut_val, width=8, signed=True)
        self.assertEqual(vsc_val, -1)
        
        # Simulating a DUT returning 0xFF from an 8-bit unsigned register
        dut_val = 0xFF
        vsc_val = ValueInt.from_bits(dut_val, width=8, signed=False)
        self.assertEqual(vsc_val, 255)
