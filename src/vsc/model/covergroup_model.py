'''
Created on Aug 3, 2019

@author: ballance
'''

class CovergroupModel():
    
    def __init__(self):
        self.coverpoint_l = []
        self.cross_l = []
        self.name = "<default>"
    
    def sample(self):
        
        # First, sample the coverpoints
        for cp in self.coverpoint_l:
            cp.sample()
            
        for cr in self.cross_l:
            cr.sample()
            
    def dump(self, ind=""):
        print(ind + "Covergroup " + self.name)
        for cp in self.coverpoint_l:
            cp.dump(ind + "    ")
        for cr in self.cross_l:
            cr.dump(ind + "    ")
            