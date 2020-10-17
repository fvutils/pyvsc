'''
Created on Mar 7, 2020

@author: ballance
'''

from unittest import TestCase
from vsc.impl import ctor
import random


class VscTestCase(TestCase):
   
    def setUp(self):
        random.seed(0)
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()