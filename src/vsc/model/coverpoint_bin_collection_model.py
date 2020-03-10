
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



'''
Created on Aug 6, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase
from _functools import reduce

class CoverpointBinCollectionModel(CoverpointBinModelBase):
    
    def __init__(self, name):
        super().__init__(name)
        self.bin_l = []
        self.hit_bin_idx = -1
        self.n_bins = -1
        
    def finalize(self):
        super().finalize()
        self.n_bins = reduce(lambda x,y: x+y, map(lambda b: b.get_n_bins(), self.bin_l))
        for b in self.bin_l:
            b.finalize()
    
    def add_bin(self, bin_m):
        bin_m.parent = self
        self.bin_l.append(bin_m)
        
    def get_coverage(self):
        coverage = 0.0
        
        for bin in self.bin_l:
            coverage += bin.get_coverage()
            
#        coverage /= len(self.bin_l)
        
        return coverage
        
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
        b = None
        for i in range(len(self.bin_l)):
            b = self.bin_l[i]
            if b.get_n_bins() > idx:
                break;
            idx -= b.get_n_bins()
            
        return b.get_hits(idx)
        
    def get_n_bins(self):
        return self.n_bins
    
    def hit_idx(self):
        return self.hit_bin_idx
    
    def accept(self, v):
        v.visit_coverpoint_bin_collection(self)

    def equals(self, oth)->bool:
        eq = isinstance(oth, CoverpointBinCollectionModel)
        
        if eq:
            eq &= super().equals(oth)
            
            if len(self.bin_l) == len(oth.bin_l):
                for i in range(len(self.bin_l)):
                    eq &= self.bin_l[i].equals(oth.bin_l[i])
            
        return eq
    
    def clone(self)->'CoverpointBinCollectionModel':
        ret = CoverpointBinCollectionModel(self.name)
        
        for bn in self.bin_l:
            ret.add_bin(bn.clone())

        return ret
