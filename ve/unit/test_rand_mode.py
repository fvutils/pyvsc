'''
Created on Jul 16, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase


class TestRandMode(VscTestCase):
    
    def test_smoke(self):
        
        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
        # First, test that values vary
        init_a = 0
        init_b = 0
        it = my_cls()
        
        for i in range(20):
            with it.randomize_with():
                it.a != init_a
                it.b != init_b
                
            self.assertNotEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a 
            init_b = it.b 
            
        # Now, disable rand_mode for a
        with vsc.raw_mode():
            it.a.rand_mode = False
        
            self.assertEqual(it.a.rand_mode, False)
            self.assertEqual(it.b.rand_mode, True)
        
        for i in range(20):
            with it.randomize_with():
                it.b != init_b
                
            self.assertEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a 
            init_b = it.b 
            
        # Now, go back
        with vsc.raw_mode():
            it.a.rand_mode = True
        
            self.assertEqual(it.a.rand_mode, True)
            self.assertEqual(it.b.rand_mode, True)

        for i in range(20):
            with it.randomize_with():
                it.a != init_a
                it.b != init_b
                
            self.assertNotEqual(it.a, init_a)
            self.assertNotEqual(it.b, init_b)
            init_a = it.a 
            init_b = it.b         

#     def full_obj(self):
#          
#         @vsc.randobj
#         class sub_cls(object):
#              
#             def __init__(self):
#                 self.a = vsc.rand_uint8_t()
#                 self.b = vsc.rand_uint8_t()
#                  
#          
#         @vsc.randobj
#         class my_cls(object):
#              
#             def __init__(self):
#                 self.a = vsc.rand_uint8_t()
#                 self.b = vsc.rand_uint8_t()
#                  
#         # First, test that values vary
#         init_a = 0
#         init_b = 0
#         it = my_cls()
#          
#         for i in range(20):
#             with it.randomize_with():
#                 it.a != init_a
#                 it.b != init_b
#                  
#             self.assertNotEqual(it.a, init_a)
#             self.assertNotEqual(it.b, init_b)
#             init_a = it.a 
#             init_b = it.b 
#              
#         # Now, disable rand_mode for the entire object
#         it.rand_mode = False
#         self.assertEqual(it.rand_mode, False)
#          
#         for i in range(20):
#             it.randomize()
#                  
#             self.assertEqual(it.a, init_a)
#             self.assertNotEqual(it.b, init_b)
#             init_a = it.a 
#             init_b = it.b 
#              
#         # Now, go back
#         with vsc.raw_mode():
#             it.a.rand_mode = True
#          
#             self.assertEqual(it.a.rand_mode, True)
#             self.assertEqual(it.b.rand_mode, True)
#  
#         for i in range(20):
#             with it.randomize_with():
#                 it.a != init_a
#                 it.b != init_b
#                  
#             self.assertNotEqual(it.a, init_a)
#             self.assertNotEqual(it.b, init_b)
#             init_a = it.a 
#             init_b = it.b         
         
