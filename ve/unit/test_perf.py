'''
Created on Jul 10, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc1.model.field_scalar_model import FieldScalarModel

class TestPerf(VscTestCase):
    
    def test_perf_smoke(self):
       
#         n_fields = 1000
#          
#         fields = []
#         for i in range(n_fields):
#             f = FieldScalarModel("a", 32, False, True)
#             fields.append(f)
#             c = 
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint32_t()
                self.b = vsc.rand_uint32_t()
                self.c = vsc.rand_uint32_t()
                self.d = vsc.rand_uint32_t()
                self.e = vsc.rand_uint32_t()
                self.f = vsc.rand_uint32_t()
                self.g = vsc.rand_uint32_t()
                self.h = vsc.rand_uint32_t()
                self.i = vsc.rand_uint32_t()
                self.j = vsc.rand_uint32_t()
                
            @vsc.constraint
            def a_c(self):
                self.a in vsc.rangelist((1,9))
                self.b in vsc.rangelist((1,9))
                self.c in vsc.rangelist((1,9))
                self.d in vsc.rangelist((1,9))
                self.e in vsc.rangelist((1,9))
                self.f in vsc.rangelist((1,9))
                self.g in vsc.rangelist((1,9))
                self.h in vsc.rangelist((1,9))
                self.i in vsc.rangelist((1,9))
                self.j in vsc.rangelist((1,9))
                
        it = my_c()
        
        count = 1000
        
        for i in range(count):
            it.randomize()
            
            