'''
Created on Aug 8, 2020

@author: ballance
'''

from enum import IntEnum, IntFlag, Flag, auto, Enum

import vsc
from .vsc_test_case import VscTestCase


class TestCoverageEnum(VscTestCase):
    
    def test_bin_names_int_enum(self):
        
        class my_e(IntEnum):
            A = auto()
            B = auto()
            
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, v):
                
                self.cp = vsc.coverpoint(v, cp_t=vsc.enum_t(my_e))

        v = my_e.A                
        cg = my_cg(lambda:v)
        cg.sample()
        v = my_e.B
        cg.sample()
        
        self.assertEqual(cg.cp.get_model().get_bin_name(0), "my_e.A")
        self.assertEqual(cg.cp.get_model().get_bin_name(1), "my_e.B")

#     def test_bin_names_enum(self):
#         
#         class my_e(Enum):
#             A = auto()
#             B = auto()
#             
#         @vsc.covergroup
#         class my_cg(object):
#             
#             def __init__(self, v):
#                 
#                 self.cp = vsc.coverpoint(v, cp_t=vsc.enum_t(my_e))
# 
#         v = my_e.A                
#         cg = my_cg(lambda:v)
#         cg.sample()
#         v = my_e.B
#         cg.sample()
#         
#         self.assertEqual(cg.cp.get_model().get_bin_name(0), "my_e.A")
#         self.assertEqual(cg.cp.get_model().get_bin_name(1), "my_e.B")        

    def test_bin_names_intflag_enum(self):
        
        class my_e(IntFlag):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self, v):
                
                self.cp = vsc.coverpoint(v, cp_t=vsc.enum_t(my_e))

        v = my_e.A                
        cg = my_cg(lambda:v)
        cg.sample()
        v = my_e.B
        cg.sample()
        v = my_e.C
        cg.sample()
        v = my_e.D
        cg.sample()
        
        self.assertEqual(cg.cp.get_model().get_bin_name(0), "my_e.A")
        self.assertEqual(cg.cp.get_model().get_bin_name(1), "my_e.B")                
        self.assertEqual(cg.cp.get_model().get_bin_name(2), "my_e.C")
        self.assertEqual(cg.cp.get_model().get_bin_name(3), "my_e.D")                
        self.assertEqual(cg.cp.get_coverage(), 100)
    
        