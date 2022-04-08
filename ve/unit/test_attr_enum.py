'''
Created on Jun 24, 2020

@author: ballance
'''
from enum import Enum, auto, IntEnum, EnumMeta

import vsc
from vsc_test_case import VscTestCase


class TestAttrEnum(VscTestCase):
    
    def test_rand_plain_enum(self):
        
        class my_e(Enum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                
        inst = my_s()
        
        for i in range(100):
            inst.randomize()

    def test_rand_plain_enum_hist(self):
        
        class my_e(Enum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                
        inst = my_s()
        
        for i in range(100):
            inst.randomize()
        
    def test_rand_int_enum(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                self.c = vsc.rand_uint8_t()

        a_hist = [0]*2
        inst = my_s()
        
        for i in range(100):
            if inst.a == my_e.A:
                a_hist[0] += 1
            else:
                a_hist[1] += 1
            inst.randomize()
            
        print("hist: " + str(a_hist))
        
        delta = abs(a_hist[0] - a_hist[1])
        self.assertLess(delta, 50)
            
    def test_rand_int_enum_hist(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @vsc.randobj
        class my_s(object):

            def __init__(self):
                self.a = vsc.rand_enum_t(my_e)
                self.b = vsc.enum_t(my_e)
                self.c = vsc.rand_uint8_t()

        a_hist = [0]*2
        
        inst = my_s()
        
        for i in range(100):
            inst.randomize()
            if inst.a == my_e.A:
                a_hist[0] += 1
            else:
                a_hist[1] += 1
                
        print("a_hist: " + str(a_hist))
        
        delta = abs(a_hist[0] - a_hist[1])
        self.assertLess(delta, 25)
       
    def test_enum_setval(self):
        class my_e(Enum):
            A = auto()
            B = auto()
        var = vsc.enum_t(my_e)
        var.set_val(my_e.A)

        self.assertEqual(var.get_val(), my_e.A)
        
    def test_enum_array(self):
        import vsc
        from enum import Enum, IntEnum, auto
        
        class riscv_reg_t(IntEnum):
            ZERO = 0
            RA = auto()
            SP = auto()
            GP = auto()
            TP = auto()
            T0 = auto()
            T1 = auto()
            T2 = auto()
            S0 = auto()
            S1 = auto()
            A0 = auto()
            A1 = auto()
            A2 = auto()
            A3 = auto()
            A4 = auto()
            A5 = auto()
            A6 = auto()
            A7 = auto()
            S2 = auto()
            S3 = auto()
            S4 = auto()
            S5 = auto()
            S6 = auto()
            S7 = auto()
            S8 = auto()
            S9 = auto()
            S10 = auto()
            S11 = auto()
            T3 = auto()
            T4 = auto()
            T5 = auto()
            T6 = auto()
        
        class compressed_gpr(IntEnum):
            S0 = 8
            S1 = auto()
            A0 = auto()
            A1 = auto()
            A2 = auto()
            A3 = auto()
            A4 = auto()
            A5 = auto()
        
        @vsc.randobj
        class my_item:
            def __init__(self):
                self.loop_cnt_reg = vsc.randsz_list_t(vsc.enum_t(riscv_reg_t))
                self.loop_init_val = vsc.randsz_list_t(vsc.int32_t())
        
            @vsc.constraint
            def loop_c(self):
                self.loop_init_val.size.inside(vsc.rangelist(1, 2))
                self.loop_cnt_reg.size.inside(vsc.rangelist(1, 2))
                self.loop_cnt_reg.size == self.loop_init_val.size
                with vsc.foreach(self.loop_init_val, idx = True ) as i:
#                    self.loop_cnt_reg[i].inside(vsc.rangelist(compressed_gpr))
                    self.loop_cnt_reg[i].inside(vsc.rangelist(list(compressed_gpr)))
        
        obj = my_item()
        obj.randomize()

    def test_enum_rangelist_exp_err(self):
        import vsc
        from enum import Enum, IntEnum, auto
        
        class riscv_reg_t(IntEnum):
            ZERO = 0
            RA = auto()
            SP = auto()
            GP = auto()
            TP = auto()
            T0 = auto()
            T1 = auto()
            T2 = auto()
            S0 = auto()
            S1 = auto()
            A0 = auto()
            A1 = auto()
            A2 = auto()
            A3 = auto()
            A4 = auto()
            A5 = auto()
            A6 = auto()
            A7 = auto()
            S2 = auto()
            S3 = auto()
            S4 = auto()
            S5 = auto()
            S6 = auto()
            S7 = auto()
            S8 = auto()
            S9 = auto()
            S10 = auto()
            S11 = auto()
            T3 = auto()
            T4 = auto()
            T5 = auto()
            T6 = auto()
        
        class compressed_gpr(IntEnum):
            S0 = 8
            S1 = auto()
            A0 = auto()
            A1 = auto()
            A2 = auto()
            A3 = auto()
            A4 = auto()
            A5 = auto()
        
        @vsc.randobj
        class my_item:
            def __init__(self):
                self.loop_cnt_reg = vsc.randsz_list_t(vsc.enum_t(riscv_reg_t))
                self.loop_init_val = vsc.randsz_list_t(vsc.int32_t())
        
            @vsc.constraint
            def loop_c(self):
                self.loop_init_val.size.inside(vsc.rangelist(1, 2))
                self.loop_cnt_reg.size.inside(vsc.rangelist(1, 2))
                self.loop_cnt_reg.size == self.loop_init_val.size
                with vsc.foreach(self.loop_init_val, idx = True ) as i:
                    # Cannot form a rangelist from an enum type
                    self.loop_cnt_reg[i].inside(vsc.rangelist(compressed_gpr))

        try:
            obj = my_item()
            self.fail("Failed to detect an attempt to use a type as a value")
        except Exception as e:
            self.assertTrue(str(e).find("Illegal attempt") != -1)

        