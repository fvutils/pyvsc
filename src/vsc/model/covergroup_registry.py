'''
Created on Dec 23, 2019

@author: ballance
'''

class CovergroupRegistry():
    
    def __init__(self):
        self.covergroup_l = []
        pass
    
    
    def accept(self, v):
        v.visit_covergroup_registry(v)