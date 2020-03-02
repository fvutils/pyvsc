'''
Created on Feb 29, 2020

@author: ballance
'''
from unittest.case import TestCase
from vsc.model.rand_obj_model import RandObjModel
from vsc.model.composite_field_model import CompositeFieldModel

class TestRandModel(TestCase):
    
    def test_smoke(self):
        
        obj = CompositeFieldModel("obj")