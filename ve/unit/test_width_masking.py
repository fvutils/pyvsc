'''
Created on Aug 15, 2020

@author: ballance
'''

import vsc
from vsc_test_case import VscTestCase

class TestWidthMasking(VscTestCase):
    
    def test_unsigned_scalar_standalone(self):
        a = vsc.uint8_t(i=1024+23)
        self.assertEqual(a.val, ((1024+23)&0xFF))

    def test_unsigned_scalar_member(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.uint8_t(i=1024)
                
        i = my_c()
        
        self.assertEqual(i.a, (1024&0xFF))
        
    def test_unsigned_scalar_member_assign(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.uint8_t(i=1024)
                
        i = my_c()
        i.a = (1024+23)
        
        self.assertEqual(i.a, ((1024+23)&0xFF))

    def test_unsigned_list_member_append(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.list_t(vsc.uint8_t())
                
        i = my_c()
        
        i.a.append((1024+23))
        
        self.assertEqual(i.a[0], ((1024+23)&0xFF))        

    def test_unsigned_list_member_assign(self):
        @vsc.randobj
        class my_c(object):
            def __init__(self):
                self.a = vsc.list_t(vsc.uint8_t(), sz=1)
                
        i = my_c()
        
        i.a[0] = (1024+23)
        
        self.assertEqual(i.a[0], ((1024+23)&0xFF))

        
        