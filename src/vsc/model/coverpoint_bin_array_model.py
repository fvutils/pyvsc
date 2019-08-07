'''
Created on Aug 3, 2019

@author: ballance
'''

class CoverpointBinArrayModel():
    
    def __init__(self, name, cp, range_l):
        n_vals = 0
        for r in range_l:
            if isinstance(r, list):
                if r[0] > r[1]:
                    raise Exception("First range element must be less than second")
                else:
                    n_vals += r[1] - r[0] + 1
            else:
                n_vals += 1
                
        self.hit_list = []
        for i in range(n_vals):
            self.hit_list.append(0)
        pass
    
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
    