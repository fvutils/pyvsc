
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


# Created on Aug 3, 2019
#
# @author: ballance

from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinEnumModel(CoverpointBinModelBase):
    
    def __init__(self, name, cp, val):
        super().__init__(name, cp)
        self.val = val
        
        self.hit_bin_idx = -1
        self.n_hits = 0
        self.cp = None

    def sample(self):
        # Query value from the actual coverpoint or expression
#        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        print("val=" + str(val) + " self.val=" + str(self.val))
        if val == self.val:
            self.hit_bin_idx = 0
            self.n_hits += 1
        else:
            self.hit_bin_idx = -1
            
        return self.hit_bin_idx
            
    def dump(self, ind=""):
        print(ind + self.name + "=" + str(self.n_hits))
            
    def get_hits(self, idx):
        return self.n_hits
        
    def get_n_bins(self):
        return 1
    
    def hit_idx(self):
        return self.hit_bin_idx    

    def accept(self, v):
        v.visit_coverpoint_bin_enum(self)
        