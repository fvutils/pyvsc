from vsc.types import rangelist
from vsc.model.rangelist_model import RangelistModel
from vsc.model.coverpoint_model import CoverpointModel

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
Created on Aug 3, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinModel(CoverpointBinModelBase):
    
    def __init__(self, parent, name, binspec : RangelistModel):
        super().__init__(parent, name)
        self.bins = []
        self.binspec = binspec
        self.hit_bin_idx = -1
        self.n_hits = 0
        
        cp = parent
        while cp is not None and not isinstance(cp, CoverpointModel):
            cp = cp.parent
            
        self.cp = cp
        
    def sample(self):
        # Query value from the actual coverpoint or expression
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
    
    