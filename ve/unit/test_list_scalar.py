'''
Created on Jun 21, 2020

@author: ballance
'''
from enum import Enum, auto, IntEnum

import vsc
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc_test_case import VscTestCase


class TestListScalar(VscTestCase):
    
    @vsc.randobj
    class my_item_c(object):
        
        def __init__(self):
            self.fixed = vsc.rand_list_t(vsc.bit_t(8), sz=4)
            self.dynamic = vsc.randsz_list_t(vsc.bit_t(8))
            self.queue = vsc.randsz_list_t(vsc.bit_t(8))
   
    
    def test_randsz_smoke(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint8_t())
                
                
            @vsc.constraint
            def l_c(self):
                self.l.size in vsc.rangelist(vsc.rng(2,10))
                self.l[1] == (self.l[0]+1)
                
        it = my_item_c()
        
        it.randomize()
        
        print("it.l.size=" + str(it.l.size))
        
        for i,v in enumerate(it.l):
            print("v[" + str(i) + "] = " + str(v))

        self.assertEqual(it.l[1], it.l[0]+1)

    def test_randsz_len(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint8_t())
                
                
            @vsc.constraint
            def l_c(self):
                self.l.size in vsc.rangelist(vsc.rng(2,10))
                self.l[1] == (self.l[0]+1)
                
        it = my_item_c()
        
        it.randomize()
        
        self.assertGreaterEqual(len(it.l), 2)
        self.assertLessEqual(len(it.l), 10)
        
        print("it.l.size=" + str(it.l.size))
        
        for i,v in enumerate(it.l):
            print("v[" + str(i) + "] = " + str(v))

        self.assertEqual(it.l[1], it.l[0]+1)

    def test_randsz_foreach_idx(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint8_t())
                self.a = vsc.rand_uint8_t()
                
                
            @vsc.constraint
            def l_c(self):
                self.l.size in vsc.rangelist(vsc.rng(2,10))
                
                with vsc.foreach(self.l, it=False, idx=True) as idx:
                    with vsc.if_then(idx > 0):
                        self.l[idx] == self.l[idx-1]+1
                
        it = my_item_c()
        
        it.randomize()
        
        for i in range(len(it.l)):
            if i > 0:
                self.assertEqual(it.l[i], it.l[i-1]+1)

    def test_fixedsz_foreach_idx(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                self.temp = vsc.list_t(vsc.uint8_t())
                self.temp = [1,3,4,12,13,14]
                
                
            @vsc.constraint
            def ab_c(self):
                self.a in vsc.rangelist(1,2,3)
                with vsc.foreach(self.temp, idx=True) as i:
                    self.a != self.temp[i]
                
        it = my_item_c()

        for i in range(10):        
            it.randomize()
            self.assertEqual(it.a, 2)
            
    def test_enum_list(self):

        class obj(object):
            def __init__(self):
                pass

        class my_e(Enum):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            
        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.vals = vsc.rand_list_t(vsc.enum_t(my_e), sz=3)
                
            @vsc.constraint
            def ab_c(self):
                pass
                
        v = my_s()

        for i in range(10):            
            v.randomize()
            print("v.vals=" + str(v.vals))
            
    def test_enum_list_unique(self):

        class obj(object):
            def __init__(self):
                pass

        class my_e(Enum):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            
        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.vals = vsc.rand_list_t(vsc.enum_t(my_e), sz=3)
                
            @vsc.constraint
            def ab_c(self):
                vsc.unique(self.vals)
                
        v = my_s()

        for i in range(10):            
            v.randomize()
            print("v.vals=" + str(v.vals))

    def test_enum_list_randsz(self):

        class obj(object):
            def __init__(self):
                pass

        class my_e(Enum):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            
        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.vals = vsc.randsz_list_t(vsc.enum_t(my_e))
                
            @vsc.constraint
            def ab_c(self):
                self.vals.size > 0
                
        v = my_s()

        for i in range(10):            
            with v.randomize_with() as it:
                it.vals.size == (i+1)
            self.assertEqual(it.vals.size, i+1)
            print("v.vals=" + str(v.vals))

    def test_list_unique(self):

        @vsc.randobj
        class my_s(object):
            
            def __init__(self):
                super().__init__()
                self.vals = vsc.rand_list_t(vsc.uint8_t(), sz=16)
                
            @vsc.constraint
            def ab_c(self):
                with vsc.foreach(self.vals) as it:
                    it < 64
                vsc.unique(self.vals)
                
        v = my_s()

        for i in range(10):
            v.randomize()
            print("v.vals=" + str(v.vals))

    def disabled_test_sum_simple(self):
        
        @vsc.randobj
        class my_item_c(object):
            
            def __init__(self):
                self.l = vsc.rand_list_t(vsc.uint8_t(), sz=5)
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def sum_c(self):
                self.l.sum == 5
                
                with vsc.foreach(self.l) as it:
                    it != 0
                
        it = my_item_c()
        it.randomize()
        print("Model: " + ModelPrettyPrinter.print(it.get_model()))
        
        self.assertEqual(it.l.sum, 5)
        
    def test_transitive_size_relationship(self):
        """Two arrays are sized using two rand fields
        that are constrained to a single value"""
        class reg_t(IntEnum):
            A = 0
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            F = auto()
            G = auto()


        @vsc.randobj
        class my_c:
            def __init__(self):
                self.offset = vsc.randsz_list_t(vsc.int32_t())
                self.reg = vsc.randsz_list_t(vsc.enum_t(reg_t))
                self.num_of_regs = vsc.rand_uint32_t()
                self.reserved_regs = vsc.randsz_list_t(vsc.enum_t(reg_t))
                self.max_offset = vsc.rand_uint32_t()


            @vsc.constraint
            def num_of_reg_c(self):
                self.num_of_regs == 2
                self.reserved_regs.size == 3
    
            @vsc.constraint
            def reg_c(self):
                vsc.solve_order(self.num_of_regs, self.reg)
                self.reg.size == self.num_of_regs
                self.offset.size == self.num_of_regs
                
                with vsc.foreach(self.reg, idx=True) as i:
                    self.reg[i].not_inside(vsc.rangelist(self.reserved_regs, reg_t.A))
                vsc.unique(self.reg)

            @vsc.constraint
            def offset_c(self):
                with vsc.foreach(self.offset, idx=True) as i:
                    self.offset[i] in vsc.rangelist(vsc.rng(0, self.max_offset - 1))

        obj = my_c()
        for i in range(20):
            obj.randomize()
            print(obj.reg)
            print(obj.num_of_regs)
            print(obj.offset)        
        