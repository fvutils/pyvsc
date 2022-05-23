'''
Created on Sep 16, 2020

@author: ballance
'''
import vsc

from vsc_test_case import VscTestCase
from enum import Enum, IntEnum, auto


class TestInlineRandomization(VscTestCase):
    
    def test_1(self):
        class level_t(IntEnum):
            LOW = auto()
            MEDIUM = auto()
            HIGH = auto()
            
        @vsc.randobj
        class solution:
            def __init__(self):
                self.num = vsc.rand_bit_t(8)
                self.level = vsc.rand_enum_t(level_t)
                self.addr = []
                self.offset = []

            def randomize_offset(self):
                print("randomize_offset " + str(self.num))
                addr_ = vsc.rand_int32_t()
                offset_ = vsc.rand_int32_t()
                self.offset = [0] * self.num
                self.addr = [0] * self.num
                for i in range(self.num):
                    try:
                        with vsc.randomize_with(addr_, offset_):
                            if self.level == level_t.LOW:
                                offset_.inside(vsc.rangelist(vsc.rng(-256,256)))
                            elif self.level == level_t.MEDIUM:
                                offset_.inside(vsc.rangelist(vsc.rng(-512,512)))
                            elif self.level == level_t.HIGH:
                                offset_.inside(vsc.rangelist(vsc.rng(-1024,1024)))
                            addr_ == self.num + offset_
                            addr_.inside(vsc.rangelist(vsc.rng(0,32)))
                    except vsc.SolveFailure as e:
                        print("Cannot Randomize offset: " + e.diagnostics)

                    self.offset[i] = offset_
                    self.addr[i] = addr_

            def post_randomize(self):
                print("post_randomize")
                self.randomize_offset()
                    
        sol = solution()
        sol.randomize()
        
    def test_inline_foreach_enum(self):

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj 
        class my_c(object):
            
            def __init__(self):
                self.ef = vsc.rand_enum_t(my_e)
                self.arr = vsc.rand_list_t(vsc.enum_t(my_e), 10)

        it = my_c()
        
        with it.randomize_with():
            with vsc.foreach(it.arr, idx=True) as i:
                it.arr[i].inside(vsc.rangelist(my_e.B))
                
    def test_2(self):
        @vsc.randobj
        class my_sub_s(object):
            def __init__(self):
                self.has_rs1 = vsc.uint8_t(1)
                self.has_rs2 = vsc.uint8_t(1)
                self.has_rd = vsc.uint8_t(1)
                self.avail_regs = vsc.rand_list_t(vsc.uint8_t(0), 10)
                self.reserved_rd = vsc.rand_list_t(vsc.uint8_t(0), 10)
                self.reserved_regs = vsc.rand_list_t(vsc.uint8_t(0), 10)
                self.rd = vsc.rand_uint8_t(0)
                self.rs1 = vsc.rand_uint8_t(0)
                self.rs2 = vsc.rand_uint8_t(0)
                self.format = vsc.uint8_t(2)

        obj = my_sub_s()
        
        with obj.randomize_with() as it:
            with vsc.if_then(obj.avail_regs.size > 0): 
                with vsc.if_then(obj.has_rs1):
                    obj.rs1.inside(vsc.rangelist(obj.avail_regs))
                with vsc.if_then(obj.has_rs2):
                    obj.rs2.inside(vsc.rangelist(obj.avail_regs))
                with vsc.if_then(obj.has_rd):
                    obj.rd.inside(vsc.rangelist(obj.avail_regs))   
            with vsc.foreach(obj.reserved_rd, idx=True) as i:
                with vsc.if_then(obj.has_rd):
                    obj.rd != obj.reserved_rd[i]
                with vsc.if_then(obj.format == 2):
                    obj.rs1 != obj.reserved_rd[i]
            with vsc.foreach(obj.reserved_regs, idx=True) as i:
                with vsc.if_then(obj.has_rd):
                    obj.rd != obj.reserved_regs[i]
                with vsc.if_then(obj.format == 2):
                    obj.rs1 != obj.reserved_regs[i]        
                

            