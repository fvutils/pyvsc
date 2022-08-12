'''
Created on Mar 7, 2020

@author: ballance
'''

from unittest import TestCase
import random
import vsc


class VscTestCase(TestCase):
   
    def setUp(self):
        random.seed(0)
        vsc.test_setup()
        
    def tearDown(self):
        vsc.test_teardown()