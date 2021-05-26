'''
Created on Aug 20, 2020

@author: ballance
'''
from enum import IntEnum, auto

import vsc
from vsc.model.rand_info_builder import RandInfoBuilder
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc_test_case import VscTestCase


class TestConstraintSolveOrder(VscTestCase):
    
    def test_depth_insufficient(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                vsc.solve_order(self.a, self.b)


        caught_exception = False
        try:
            i = my_c()
        except Exception:
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order outside constraint")
                
    def test_depth_excessive(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                with vsc.if_then(self.a < self.b):
                    self.b == 10
                    vsc.solve_order(self.a, self.b)                

        caught_exception = False
        try:
            i = my_c()
        except Exception:
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order buried in a constraint")
        
    def test_incorrect_args(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(1, self.b)
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        caught_exception = False
        try:
            i = my_c()
        except Exception as e:
            print("Exception: " + str(e))
            caught_exception = True
            pass
        self.assertTrue(caught_exception, "Failed to detect solve_order incorrect arguments")

    # We've changed the way that ordering constraints are handled
    def disabled_test_order_model_1(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)
                self.a < self.b
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        i = my_c()
        
#        i.randomize()
        model = i.get_model()
        model.set_used_rand(True)
        info = RandInfoBuilder.build([model], [])
        self.assertEqual(len(info.randset_l), 2)
        a = model.find_field("a")
        b = model.find_field("b")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIn(a, info.randset_l[0].fields())
        self.assertIn(b, info.randset_l[1].fields())

    def disabled_test_order_model_2(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                self.c = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.b, self.c)
                vsc.solve_order(self.a, self.b)

                self.b < 30                
                self.a < 20
                with vsc.if_then(self.a == 0):
                    self.b < 10
                    

        i = my_c()
        
#        i.randomize()
        model = i.get_model()
        model.set_used_rand(True)
        info = RandInfoBuilder.build([model], [])
        
        self.assertEqual(len(info.randset_l), 3)
        a = model.find_field("a")
        b = model.find_field("b")
        c = model.find_field("c")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNotNone(c)
        self.assertIn(a, info.randset_l[0].fields())
        self.assertIn(b, info.randset_l[1].fields())
        self.assertIn(c, info.randset_l[2].fields())
        
        self.assertEqual(len(info.randset_l[0].constraints()), 2)
        self.assertEqual(len(info.randset_l[1].constraints()), 2)
        self.assertEqual(len(info.randset_l[2].constraints()), 0)

    def test_order_hist_1(self):
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)

                with vsc.if_then(self.a == 0):
                    self.b == 4
                with vsc.else_then:
                    self.b != 4
                    

        i = my_c()
        
        a_hist = [0]*2
        b_hist = [0]*2

        for x in range(100):
            i.randomize()
            a_hist[i.a] += 1
#            print("i.a=" + str(i.a) + " i.b=" + str(i.b))
            b_hist[0 if i.b == 4 else 1] += 1
            
        print("a_hist: " + str(a_hist))
        print("b_hist: " + str(b_hist))
        
    def test_order_list(self):
        class my_e(IntEnum):
            ZERO = 0
            ONE = auto()
            TWO = auto()
            
        @vsc.randobj
        class my_c:
            def __init__(self):
                self.s = 7
                self.a = vsc.randsz_list_t(vsc.rand_uint8_t())
                self.b = vsc.rand_list_t(vsc.enum_t(my_e), 5)
                
            @vsc.constraint
            def my_const(self):
                vsc.solve_order(self.b, self.a)
                self.a.size == self.s
                
        obj = my_c()
        for i in range(5):
            obj.randomize()
            print(obj.a, obj.b)
            
    def test_max_load_store_offset(self):
        @vsc.randobj
        class mem_region_t:
            def __init__(self, name = "", size_in_bytes = 0, xwr = 0): 
                self.name = name 
                self.size_in_bytes = vsc.uint32_t(i = size_in_bytes)
                self.xwr = vsc.uint8_t(i = xwr)

        @vsc.randobj
        class classA:
            def __init__(self):
                self.base = vsc.rand_int32_t()
                self.max_load_store_offset = vsc.rand_int32_t()
                self.max_data_page_id = vsc.int32_t()
                self.data_page = vsc.list_t(mem_region_t())
                self.data_page_id = vsc.rand_uint32_t()
                self.mem_region = vsc.list_t(mem_region_t())
                self.mem_region.extend([mem_region_t(name = "region_0", size_in_bytes = 4096, xwr = 8), 
                                        mem_region_t(name = "region_1", size_in_bytes = 4096, xwr = 8)])

            def pre_randomize(self):
                print("[Pre] max_load_store_offset: ", self.max_load_store_offset)
                print("[Pre] Base: ", self.base)
                self.data_page.clear()
                self.data_page.extend(self.mem_region)
                self.max_data_page_id = len(self.data_page)
        

            def post_randomize(self):
                print("[Post] max_load_store_offset: ", self.max_load_store_offset)
                print("[Post] Base: ", self.base)

            @vsc.constraint
            def addr_c(self):
                vsc.solve_order(self.data_page_id, self.max_load_store_offset)
                vsc.solve_order(self.max_load_store_offset, self.base)
                self.data_page_id < self.max_data_page_id
                with vsc.foreach(self.data_page, idx = True) as i:
                    with vsc.if_then(i == self.data_page_id):
                        self.max_load_store_offset == self.data_page[i].size_in_bytes
                self.base in vsc.rangelist(vsc.rng(0, self.max_load_store_offset - 1))

        obj = classA()
        for i in range(100):
            obj.randomize()

    def test_num_of_tested_loop_randomiation(self):
        import vsc
        from enum import Enum,auto

        @vsc.randobj
        class riscv_instr:
            def __init__(self):
                self.temp = vsc.rand_uint8_t()


        class my_e(Enum):
            A = 0
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            F = auto()
            G = auto()

        @vsc.randobj
        class riscv_loop_instr:
            def __init__(self):
                self.loop_cnt_reg = vsc.randsz_list_t(vsc.enum_t(my_e))
                self.loop_limit_reg = vsc.randsz_list_t(vsc.enum_t(my_e))
                self.loop_init_val = vsc.randsz_list_t(vsc.uint32_t())
                self.loop_step_val = vsc.randsz_list_t(vsc.uint32_t())
                self.loop_limit_val = vsc.randsz_list_t(vsc.uint32_t())
                self.num_of_nested_loop = vsc.rand_bit_t(3)
                self.num_of_instr_in_loop = vsc.rand_uint32_t()
                self.branch_type = vsc.randsz_list_t(vsc.enum_t(my_e))

            @vsc.constraint
            def legal_loop_regs_c(self):
                vsc.solve_order(self.num_of_nested_loop, self.loop_init_val)
                vsc.solve_order(self.num_of_nested_loop, self.loop_step_val)
                vsc.solve_order(self.num_of_nested_loop, self.loop_limit_val)
                vsc.solve_order(self.loop_limit_val, self.loop_limit_reg)
                vsc.solve_order(self.branch_type, self.loop_init_val)
                vsc.solve_order(self.branch_type, self.loop_step_val)
                vsc.solve_order(self.branch_type, self.loop_limit_val)
                self.num_of_instr_in_loop.inside(vsc.rangelist((1, 25)))
                self.num_of_nested_loop.inside(vsc.rangelist(1, 2))
                self.loop_init_val.size == self.num_of_nested_loop
                self.loop_step_val.size == self.num_of_nested_loop
                self.loop_limit_val.size == self.num_of_nested_loop
                self.loop_init_val.size == self.num_of_nested_loop
                self.branch_type.size == self.num_of_nested_loop
                self.loop_step_val.size == self.num_of_nested_loop
                self.loop_limit_val.size == self.num_of_nested_loop
                self.branch_type.size == self.num_of_nested_loop

            @vsc.constraint
            def loop_c(self):
                vsc.solve_order(self.num_of_nested_loop, self.loop_cnt_reg)
                vsc.solve_order(self.num_of_nested_loop, self.loop_limit_reg)
                self.loop_cnt_reg.size == self.num_of_nested_loop
                self.loop_limit_reg.size == self.num_of_nested_loop


        obj = riscv_loop_instr()
        num_of_nested_loop_hist = [0]*3
        for i in range(10):
            obj.randomize(debug=0)
            num_of_nested_loop_hist[obj.num_of_nested_loop] += 1

        print("hist: " + str(num_of_nested_loop_hist))
        self.assertEqual(0, num_of_nested_loop_hist[0])
        self.assertNotEqual(0, num_of_nested_loop_hist[1])
        self.assertNotEqual(0, num_of_nested_loop_hist[2])

