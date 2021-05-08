'''
Created on Aug 8, 2020

@author: ballance
'''
from enum import IntEnum, auto, Enum

import vsc
from vsc_test_case import VscTestCase


class TestCovergroupSampling(VscTestCase):
    
    def test_sample_nonvsc_object_local_lambda(self):
        class my_e(IntEnum):
            A = auto()
            B = auto()


        class my_c:
            def __init__(self):
                self.a = 5
                self.b = my_e.A


        @vsc.covergroup
        class my_cg(object):
            def __init__(self, input):
                super().__init__()
#                self.cp1 = vsc.coverpoint(lambda : input.a,
#                                bins=dict(
#                               a=vsc.bin_array([], [1, 15])
#                               ))
                self.cp2 = vsc.coverpoint(lambda : input.b, 
                                        cp_t=vsc.enum_t(my_e))

        inst = my_c()
        cg = my_cg(inst)
        inst.b = my_e.A
        cg.sample()
        inst.b = my_e.B
        cg.sample()
        vsc.report_coverage(details=True)
        self.assertEquals(cg.cp2.get_coverage(), 100)
        
#     def test_sample_nonvsc_object_local_lambda_enum(self):
#         class my_e(Enum):
#             A = auto()
#             B = auto()
# 
# 
#         class my_c:
#             def __init__(self):
#                 self.a = 5
#                 self.b = my_e.A
# 
# 
#         @vsc.covergroup
#         class my_cg(object):
#             def __init__(self, input):
#                 super().__init__()
#                 self.cp1 = vsc.coverpoint(lambda : input.a,
#                                 bins=dict(
#                                 a=vsc.bin_array([], [1, 15])
#                                 ))
#                 self.cp2 = vsc.coverpoint(lambda : input.b, 
#                                         cp_t=vsc.enum_t(my_e))
# 
#         inst = my_c()
#         cg = my_cg(inst)
#         inst.b = my_e.A
#         print("inst.b=" + str(inst.b))
#         cg.sample()
#         inst.b = my_e.B
#         print("inst.b=" + str(inst.b))
#         cg.sample()
#         vsc.report_coverage(details=True)        

#     def test_sample_vsc_object(self):
#         class my_e(IntEnum):
#             A = auto()
#             B = auto()
# 
# 
#         @vsc.randobj
#         class my_c:
#             def __init__(self):
#                 self.a = 5
#                 self.b = my_e.A
# 
# 
#         @vsc.covergroup
#         class my_cg(object):
#             def __init__(self, input):
#                 super().__init__()
#                 self.cp1 = vsc.coverpoint(input.a,
#                                 bins=dict(
#                                 a=vsc.bin_array([], [1, 15])
#                                 ))
#                 self.cp2 = vsc.coverpoint(input.b, cp_t=vsc.enum_t(my_e))
# 
#         inst = my_c()
#         cg = my_cg(inst)
#         inst.b = my_e.A
#         cg.sample()
#         inst.b = my_e.B
#         cg.sample()
#         vsc.report_coverage(details=True)
        
    def test_sample_vsc_object_with_sample(self):
        @vsc.randobj
        class my_c:
            def __init__(self):
                self.a = vsc.uint32_t(i=0)
                self.b = vsc.uint32_t(i=0)
 
 
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                super().__init__()
                self.with_sample(dict(
                    input=my_c())
                    )
                self.cp1 = vsc.coverpoint(self.input.a,
                                bins=dict(
                                a=vsc.bin_array([], [1, 15])
                                ))
                self.cp2 = vsc.coverpoint(self.input.b, 
                                bins=dict(
                                    b=vsc.bin_array([], [1,15])
                                ))
 
        inst = my_c()
        cg = my_cg()
        inst.a = 1
        inst.b = 1
        cg.sample(inst)
        inst.a = 2
        inst.b = 2
        cg.sample(inst)
        vsc.report_coverage(details=True)
        report = vsc.get_coverage_report_model()

        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].coverpoints), 2)
        self.assertEqual(report.covergroups[0].coverpoints[0].coverage, 13.33)
        self.assertEqual(report.covergroups[0].coverpoints[1].coverage, 13.33)


    def test_cross_sampling(self):
        @vsc.covergroup
        class my_cg(object):

            def __init__(self, a, b):
                super().__init__()

                self.cp1 = vsc.coverpoint(a, bins={
                    "a": vsc.bin_array([], [1, 10])
                })
                self.cp2 = vsc.coverpoint(b, bins={
                    "b": vsc.bin_array([], [1, 10])
                })
                self.cp1X2 = vsc.cross([self.cp1, self.cp2])


        a = 6
        b = 8
        cg = my_cg(lambda: a, lambda: b)

        for i in range(50):
            cg.sample()

        vsc.report_coverage(details=True)
#        vsc.report_coverage(details=False)
        print("Coverage: " + str(cg.get_coverage()))

        