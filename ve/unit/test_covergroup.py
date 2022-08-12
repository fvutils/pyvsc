
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
'''
Created on Aug 4, 2019

@author: ballance
'''

import vsc
from builtins import range, callable
from enum import IntEnum
import unittest
from unittest.case import TestCase
from .vsc_test_case import VscTestCase

class TestCovergroup(VscTestCase):
    
    def test_simple_coverpoint(self):

        @covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4)
                    ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })
                
        cg = my_covergroup()
        
        cg.sample(5)
        cg.sample(4)
        cg.sample(4)
        
        
    def test_ref_covergroup(self):
        
        class my_e(IntEnum):
            A = auto()
            B = auto()

        @covergroup
        class my_covergroup(object):
            
            def __init__(self, a, b, c): # Need to use lambda for non-reference values
                super().__init__()
                self.type_options.weight = 1
                self.options.auto_bin_max = 32
                
                self.cp1 = coverpoint(a, 
                    options=dict(
                        auto_bin_max=64
                    ),
                    bins=dict(
                        a = bin_array([], [1,15])
                    ))
                
                self.cp2 = coverpoint(b, bins=dict(
                    b = bin_array([], [1,15])
                    ))
                
                self.cp3 = coverpoint(c, cp_t=enum_t(my_e))
                
        a = 1;
        b = 2;
        c = my_e.A
        
        cg = my_covergroup(lambda:a, lambda:b, lambda:c)
        
        cg.sample()
        a = 2
        c = my_e.B
        cg.sample()
        a = 3
        cg.sample()
        
    def test_emb_covergroup(self):

        @vsc.randobj        
        class my_item_c(object):

            @covergroup
            class my_covergroup():
                def __init__(self, it): # Reference values can be passed directly
                    super().__init__()
                
                    self.cp1 = coverpoint(it.a, bins={
                        "a" : bin_array([], [1,15])
                    })
            
            def __init__(self):
                self.a = rand_bit_t(8)
                self.cg = my_item_c.my_covergroup(self)

                self.a = 1
                self.cg.sample()
                self.a = 2
                self.cg.sample()
                self.a = 3
                self.cg.sample()
                
        c = my_item_c()
        c.randomize()
        c.cg.sample()
        
    def disabled_test_plain_obj_sample(self):

        class my_item_c(object):
            
            def __init__(self):
                self.a = 0
                self.b = 0
                
            
        @covergroup
        class my_covergroup(object):
            def __init__(self):
                
                self.with_sample(
                    it=my_item_c()
                    )
             
                self.cp1 = coverpoint(self.it.a, bins={
                        "a" : bin_array([], [1,15])
                    })
                self.cp1 = coverpoint(self.it.b, bins={
                        "b" : bin_array([], [1,15])
                    })
            
        cg = my_covergroup()
        it1 = my_item_c()
        it2 = my_item_c()

        for i in range(1,16):
            it1.a = i
            cg.sample(it1)
        for i in range(1,16):
            it2.b = i
            cg.sample(it2)
            
        

    def disabled_test_covergroup_inheritance(self):

        @randobj
        class my_item_c():

            @covergroup
            class my_covergroup(object):
                def __init__(self, it): # Reference values can be passed directly
                    super().__init__()
                    
                    self.with_sample(dict(
                        c=uint8_t(),
                        d=uint8_t()))

                    self.options.per_instance = True
                
                    self.cp1 = coverpoint(it.a, bins={
                        "a" : bin_array([], [1,15])
                    })

            @covergroup
            class my_covergroup2(my_covergroup):
                def __init__(self, it): # Reference values can be passed directly
                    super().__init__(it)
                
                    self.cp2 = coverpoint(it.a, bins={
                        "b" : bin_array([], [1,3])
                    })
                    
                    self.cp3 = coverpoint(self.c, bins={
                        "c" : bin_array([], [1,3])
                    })

                    print("cp1=" + str(self.cp1) + " cp2=" + str(self.cp2))
                    self.cp1_cp2 = cross([self.cp1, self.cp2])
            
            def __init__(self):
                self.a = rand_bit_t(8)
                self.cg = my_item_c.my_covergroup2(self)

                self.a = 1
                self.cg.sample(1,2)
                self.a = 2
                self.cg.sample(2,3)
                self.a = 3
                self.cg.sample(3,4)
                
        c = my_item_c()
        print("Coverage: " + str(c.cg.get_coverage()))
                
    def test_class_covergroup(self):
       
        @randobj
        class my_rand():
            
            def __init__(self):
                self.a = rand_bit_t(4)
                self.b = rand_bit_t(4)

        @covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    cls=my_rand()
                ))
                self.cp1 = coverpoint(self.cls.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                
        cg = my_covergroup()
        
        cls = my_rand()
        cls.a <= 4

        cg.sample(cls)
        
        
    def test_simple_cross(self):
      
        @covergroup
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4),
                    b=bit_t(4)
                ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                self.cp2 = coverpoint(self.b, bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp1X2 = cross([self.cp1, self.cp2])

        cg = my_covergroup()
        
        for i in range(1000):
            cg.sample(4, 4)
            cg.sample(4, 4)
         
            cg.sample(8, 8)
            cg.sample(8, 8)
        
        
    def test_binsof_cross(self):
      
        @covergroup
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4),
                    b=bit_t(4)
                ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                self.cp2 = coverpoint(self.b, bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp1X2 = cross([self.cp1, self.cp2], bins={
#                    "a" : binsof(self.cp1.a).intersect([0,1,range(5,7)]) and binsof(self.cp2.a)
                    })

        cg = my_covergroup()
        
        for i in range(1000):
            cg.sample(4, 4)
            cg.sample(4, 4)
         
            cg.sample(8, 8)
            cg.sample(8, 8)

    def test_mult_instances(self):
        @vsc.covergroup
        class my_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))

                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a_bins=vsc.bin_array([4], [0, 16])
                ))

        my_cg_1 = my_cg()
        my_cg_2 = my_cg()

        for i in range(8):
            my_cg_1.sample(i, 0)

        for i in range(16):
            my_cg_2.sample(i, 0)

        str_report = vsc.get_coverage_report(details=True)
        print("Report:\n" + str_report)
        
        report = vsc.get_coverage_report_model()
        self.assertEqual(1, len(report.covergroups))
        self.assertEquals(2, len(report.covergroups[0].covergroups))
        self.assertEquals(100, report.covergroups[0].coverage)
        self.assertEquals(50, report.covergroups[0].covergroups[0].coverage)
        self.assertEquals(100, report.covergroups[0].covergroups[1].coverage)
        
    def test_inheritance_not_supported(self):
        caught_exception = False
        
        try:
            @vsc.covergroup
            class main_cg(object):
                def __init__(self, it):
                    super().__init__()

                    self.cp1 = vsc.coverpoint(it, bins={
                        "a": vsc.bin(5)
                    })


            @vsc.covergroup
            class first_extended_cg(main_cg):
                def __init__(self, it):
                    super().__init__(it)

                    self.cp2 = vsc.coverpoint(it, bins={
                        "a": vsc.bin(7)
                    })

            var = 5
            cg = first_extended_cg(lambda:var)
        except Exception as e:
            caught_exception = True
            pass
        
        self.assertTrue(caught_exception)
        
    def test_covergroup_set_name(self):
        
        @vsc.covergroup
        class cg_t(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t()
                    ))
                self.cp = vsc.coverpoint(self.a)
                
        cg1 = cg_t()
        cg1.set_name("cg1")
        cg2 = cg_t()
        cg2.set_name("cg2")

        vsc.report_coverage()
        report = vsc.get_coverage_report_model()
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].covergroups), 2)
        self.assertEqual(report.covergroups[0].covergroups[0].name, "cg1")
        self.assertEqual(report.covergroups[0].covergroups[1].name, "cg2")

    def test_covergroup_name_option(self):
        
        @vsc.covergroup
        class cg_t(object):
            
            def __init__(self, name):
                self.with_sample(dict(
                    a=vsc.uint8_t()
                    ))
                self.options.name = name
                self.cp = vsc.coverpoint(self.a)
                
        cg1 = cg_t("cg1")
        cg2 = cg_t("cg2")

        vsc.report_coverage()
        report = vsc.get_coverage_report_model()
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].covergroups), 2)
        self.assertEqual(report.covergroups[0].covergroups[0].name, "cg1")
        self.assertEqual(report.covergroups[0].covergroups[1].name, "cg2")
            
    def test_covergroup_setname_init(self):
        
        @vsc.covergroup
        class cg_t(object):
            
            def __init__(self, name):
                self.with_sample(dict(
                    a=vsc.uint8_t()
                    ))
                self.set_name(name)
                self.cp = vsc.coverpoint(self.a)
                
        cg1 = cg_t("cg1")
        cg2 = cg_t("cg2")

        vsc.report_coverage()
        report = vsc.get_coverage_report_model()
        self.assertEqual(len(report.covergroups), 1)
        self.assertEqual(len(report.covergroups[0].covergroups), 2)
        self.assertEqual(report.covergroups[0].covergroups[0].name, "cg1")
        self.assertEqual(report.covergroups[0].covergroups[1].name, "cg2")

    
