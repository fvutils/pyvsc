'''
Created on Feb 7, 2020

@author: ballance
'''
from vsc.model import enter_expr_mode, leave_expr_mode

class CovergroupInt():
    """Internal data used by a covergroup """
    
    def __init__(self, facade_obj):
        print("covergroup_int")
        self.fo = facade_obj
        self.sample_var_l = []
        self.model = None
        self.ctor_level = 0
        self.locked = False
        pass
    
    def __enter__(self):
        enter_expr_mode()
        self.ctor_level += 1
        
    def __exit__(self, t, v, tb):
        leave_expr_mode()
        self.ctor_level -= 1
        