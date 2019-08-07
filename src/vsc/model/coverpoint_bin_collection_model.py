'''
Created on Aug 6, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinCollectionModel(CoverpointBinModelBase):
    
    def __init__(self, name, cp):
        super().__init__(name, cp)
        self.bin_l = []
        
    def sample(self):
        
        for b in self.bin_l:
            b.sample()
            
        # Query value from the actual coverpoint or expression
        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        if val in self.binspec:
            self.hit_bin_idx = 0
            self.n_hits += 1
        else:
            self.hit_bin_idx = -1
            
    def dump(self, ind=""):
        print(ind + "Bins " + self.name)
        for b in self.bin_l:
            b.dump(ind + "    ")
            
    def get_hits(self, idx):
        # TODO
        return self.n_hits
        
    def get_n_bins(self):
        return 1
    
    def hit_idx(self):
        return self.hit_bin_idx