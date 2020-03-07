'''
Created on Mar 7, 2020

@author: ballance
'''

from unittest import TestCase
from vsc.impl import ctor

class VscTestCase(TestCase):
   
    def setUp(self):
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()