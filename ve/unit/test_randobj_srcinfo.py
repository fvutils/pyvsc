'''
Created on Aug 21, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc.model.field_composite_model import FieldCompositeModel

class TestRandObjSrcInfo(VscTestCase):
    
    def test_enabled_smoke(self):
        
        @vsc.randobj(srcinfo=True)
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                pass
            
            @vsc.constraint
            def my_c(self):
                self.a < self.b

        obj = my_c()
        obj_m : FieldCompositeModel = obj.get_model()
        
        self.assertEqual(len(obj_m.constraint_model_l), 1)
        self.assertIsNotNone(obj_m.constraint_model_l[0].constraint_l[0].srcinfo)

    def test_disabled_smoke_1(self):
        
        @vsc.randobj(srcinfo=False)
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                pass
            
            @vsc.constraint
            def my_c(self):
                self.a < self.b

        obj = my_c()
        obj_m : FieldCompositeModel = obj.get_model()
        
        self.assertEqual(len(obj_m.constraint_model_l), 1)
        self.assertIsNone(obj_m.constraint_model_l[0].constraint_l[0].srcinfo)

    def test_disabled_smoke_2(self):
        
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                pass
            
            @vsc.constraint
            def my_c(self):
                self.a < self.b

        obj = my_c()
        obj_m : FieldCompositeModel = obj.get_model()
        
        self.assertEqual(len(obj_m.constraint_model_l), 1)
        self.assertIsNone(obj_m.constraint_model_l[0].constraint_l[0].srcinfo)        
        
