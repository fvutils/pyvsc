'''
Created on Jul 1, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from enum import Enum, auto, IntEnum

class TestCoverpointBins(VscTestCase):
    
    def test_bin_array_partition(self):
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t()))
                self.a_cp = vsc.coverpoint(
                    self.a, bins=dict(
                        a1=vsc.bin_array([4], (0,16))
                        ))
                
        cg = my_cg()
        cg.sample(0)
        cg.sample(3)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 25)
        cg.sample(4)
        cg.sample(7)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 50)
        
    def test_coverpoint_enum(self):
        
        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()
        
        @vsc.covergroup
        class my_cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.enum_t(my_e)))
                self.a_cp = vsc.coverpoint(self.a)
                
        cg = my_cg()
        cg.sample(my_e.A)
        cg.sample(my_e.C)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 50)
        cg.sample(my_e.D)
        cg.sample(my_e.B)
        print("coverage: " + str(cg.a_cp.get_coverage()))        
        self.assertEqual(cg.a_cp.get_coverage(), 100)
        

    def test_enum_lambda(self):

        class my_e(IntEnum):
            A = auto()
            B = auto()


        @vsc.covergroup
        class my_covergroup(object):
            def __init__(self, a, b):  # Need to use lambda for non-reference values
                super().__init__()
                self.cp1 = vsc.coverpoint(a,
                              options=dict(
                                  auto_bin_max=64
                              ),
                              bins=dict(
                                  a=vsc.bin_array([], [1, 15])
                              ))

                self.cp2 = vsc.coverpoint(b, cp_t=vsc.enum_t(my_e))


        a = 1
        b = my_e.A
        cg = my_covergroup(lambda: a, lambda: b)

        cg.sample()

        cg.dump()

        vsc.report_coverage(details=True)        
        
        