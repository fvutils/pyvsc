
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from vsc.model.coverpoint_model import CoverpointModel


'''
Created on Aug 3, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinArrayModel(CoverpointBinModelBase):
    
    def __init__(self, parent, name, low, high):
        super().__init__(parent, name)
        self.low = low 
        self.high = high 
        self.hit_bin_idx = -1
        
        cp = parent
        while cp is not None and not isinstance(cp, CoverpointModel):
            cp = cp.parent
        self.cp = cp

        self.hit_list = []
        for i in range(self.high-self.low+1):
            self.hit_list.append(0)
            
    def finalize(self):
        pass
            
    def get_coverage(self):
        coverage = 0.0
        
        for h in self.hit_list:
            coverage += 1 if h != 0 else 0

        coverage /= len(self.hit_list)
        
        return coverage
            
    def sample(self):
        # Query value from the actual coverpoint or expression
#        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        if val >= self.low and val <= self.high:
            self.hit_bin_idx = val - self.low
            self.hit_list[val-self.low] += 1
        else:
            self.hit_bin_idx = -1
            
        return self.hit_bin_idx
            
    def dump(self, ind=""):
        for i in range(self.high-self.low+1):
            print(ind + self.name + "[" + str(self.low+i) + "]=" + str(self.hit_list[i]))
            
    def get_hits(self, idx):
        return self.hit_list[idx]
        
    def get_n_bins(self):
        return (self.high-self.low+1)
    
    def hit_idx(self):
        return self.hit_bin_idx    
    