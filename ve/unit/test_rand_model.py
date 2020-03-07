'''
Created on Feb 29, 2020

@author: ballance
'''
from unittest.case import TestCase

from vsc.model.composite_field_model import CompositeFieldModel
from vsc_test_case import VscTestCase


class TestRandModel(VscTestCase):
    
    def test_smoke(self):
        
        obj = CompositeFieldModel("obj")