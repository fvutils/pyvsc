'''
Created on Dec 23, 2019

@author: ballance
'''

class CovergroupRegistry():
    
    _inst = None
    
    def __init__(self):
        self.covergroup_l = []
        pass
    
    def accept(self, v):
        v.visit_covergroup_registry(v)
        
    @staticmethod
    def inst():
        if CovergroupRegistry._inst is None:
            CovergroupRegistry._inst = CovergroupRegistry()
        return CovergroupRegistry._inst
