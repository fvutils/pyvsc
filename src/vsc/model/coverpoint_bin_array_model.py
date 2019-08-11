
#   Copyright 2019 Matthew Ballance
#   All Rights Reserved Worldwide
#
#   Licensed under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in
#   compliance with the License.  You may obtain a copy of
#   the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in
#   writing, software distributed under the License is
#   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, either express or implied.  See
#   the License for the specific language governing
#   permissions and limitations under the License.

'''
Created on Aug 3, 2019

@author: ballance
'''
from Cython.Plex.Regexps import lowercase_range
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinArrayModel(CoverpointBinModelBase):
    
    def __init__(self, name, cp, low, high):
        super().__init__(name, cp)
        self.low = low 
        self.high = high 
        self.hit_bin_idx = -1

        self.hit_list = []
        for i in range(self.high-self.low+1):
            self.hit_list.append(0)
            
    def sample(self):
        # Query value from the actual coverpoint or expression
#        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        print("CoverpointBinArrayModel::sample - val=" + str(val) + " low=" + str(self.low) + " high=" + str(self.high))
        if val >= self.low and val <= self.high:
            self.hit_bin_idx = val - self.low
            self.hit_list[val-self.low] += 1
        else:
            self.hit_bin_idx = -1
            
        return self.hit_bin_idx
            
    def dump(self, ind=""):
        print(ind + "(TODO: Array) Bin " + self.name) #  + " hits: " + str(self.n_hits))
            
    def get_hits(self, idx):
        return self.hit_list[idx]
        
    def get_n_bins(self):
        return (self.high-self.low+1)
    
    def hit_idx(self):
        return self.hit_bin_idx    
    