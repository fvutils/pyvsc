'''
Created on May 6, 2021

@author: mballance
'''
import vsc
from vsc.model.rand_if import RandIF
from vsc_test_case import VscTestCase
import random
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter


class TestCoverageDrivenConstraints(VscTestCase):
    
    def disabled_test_smoke(self):
        
        class my_r(RandIF):
            """Defines operations to be implemented by a random generator"""
    
            def __init__(self):
                super().__init__()
        
            def randint(self, low:int, high:int)->int:
                return low
    
            def sample(self, s, k):
                return random.sample(sorted(s), k)
        
        
        @vsc.randobj
        class cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint32_t()
                
        @vsc.covergroup
        class cvg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint32_t(),
                    b=vsc.uint32_t()))
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a1 = vsc.bin_array([], 1, 2, 4, 8)))
                self.b_cp = vsc.coverpoint(self.b, bins=dict(
                    b1 = vsc.bin_array([], 1, 2, 4, 8)))
                
        c = cls()
        cg = cvg()
        
        c.a = 1
        c.b = 1
        
        cg.sample(c.a, c.b)

        r = my_r()        
        bin = cg.a_cp.get_model().select_unhit_bin(r)
        rng = cg.a_cp.get_model().get_bin_range(bin)
        print("bin=" + str(bin) + " rng=" + str(rng))
        print(ModelPrettyPrinter().print(rng))
        
        vsc.report_coverage()
        
