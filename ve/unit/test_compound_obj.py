from unittest.case import TestCase
from vsc.rand_obj import RandObj
from vsc.types import rand_uint16_t
from vsc.attrs import rand_attr, attr
import vsc


class TestCompoundObj(TestCase):
    
    def test_rand_compound(self):
        
        class C1(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()
                
        class C2(RandObj):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = rand_attr(C1())
                
        c2 = C2()
        
        for i in range(10):
            c2.randomize()
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b))

    def test_rand_compound(self):
        
        class C1(RandObj):
            
            def __init__(self):
                super().__init__()
                self.a = rand_uint16_t()
                self.b = rand_uint16_t()
                
        class C2(RandObj):
            
            def __init__(self):
                super().__init__()
                self.c1 = rand_attr(C1())
                self.c2 = attr(C1())
                
                @vsc.constraint
                def c1_c2_c(self):
                    self.c1.a == self.c2.a
                
        c2 = C2()
        
        for i in range(10):
            c2.c2.a = i
            print("c2.c2.a=" + str(c2.c2.a))
            c2.randomize()  
            print("c1.a=" + str(c2.c1.a) + " c1.b=" + str(c2.c1.b) + " c2.a=" + str(c2.c2.a))    
            self.assertEqual(c2.c1.a, i)
    