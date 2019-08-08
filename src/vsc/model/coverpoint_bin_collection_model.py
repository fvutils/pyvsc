
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
Created on Aug 6, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase
from _functools import reduce

class CoverpointBinCollectionModel(CoverpointBinModelBase):
    
    def __init__(self, name, cp):
        super().__init__(name, cp)
        self.bin_l = []
        self.hit_bin_idx = -1
        self.n_bins = -1
        
    def sample(self):
        self.hit_bin_idx = -1

        idx = 0
        for b in self.bin_l:
            hit = b.sample()
            
            if hit != -1:
                self.hit_bin_idx = idx + hit
            idx += b.get_n_bins()
            
            
    def dump(self, ind=""):
        print(ind + "Bins " + self.name)
        for b in self.bin_l:
            b.dump(ind + "    ")
            
    def get_hits(self, idx):
        # TODO
        return self.n_hits
        
    def get_n_bins(self):
        return reduce(lambda x,y: x+y, map(lambda b: b.get_n_bins(), self.bin_l))
    
    def hit_idx(self):
        return self.hit_bin_idx