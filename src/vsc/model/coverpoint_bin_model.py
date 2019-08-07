'''
Created on Aug 3, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinModel(CoverpointBinModelBase):
    
    def __init__(self, name, cp, binspec):
        super().__init__(name, cp)
        self.bins = []
        self.binspec = binspec
        self.hit_bin_idx = -1
        self.n_hits = 0
        
    def sample(self):
        # Query value from the actual coverpoint or expression
        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        if val in self.binspec:
            self.hit_bin_idx = 0
            self.n_hits += 1
        else:
            self.hit_bin_idx = -1
            
    def dump(self, ind=""):
        print(ind + "Bin " + self.name + " hits: " + str(self.n_hits))
            
    def get_hits(self, idx):
        return self.n_hits
        
    def get_n_bins(self):
        return 1
    
    def hit_idx(self):
        return self.hit_bin_idx
    
    