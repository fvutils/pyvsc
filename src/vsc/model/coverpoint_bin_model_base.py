'''
Created on Aug 4, 2019

@author: ballance
'''

class CoverpointBinModelBase():
    
    def __init__(self, name, cp):
        self.name = name
        self.cp = cp
        
    def n_bins(self):
        return 1
    
    def hit_idx(self):
        return -1
